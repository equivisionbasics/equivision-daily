#!/usr/bin/env python3
"""EquiVision Basics - daily Instagram carousel publisher.

Runs inside GitHub Actions (see .github/workflows/daily-post.yml).

    python src/publish.py --mode scheduled --enforce-window   # what the daily cron runs
    python src/publish.py --mode check                        # safe test, posts nothing
    python src/publish.py --mode publish_next                 # post the next approved post right now

Safety rules built in:
  * Only posts marked "approved": true are ever published.
  * It refuses to run unless the token belongs to @equivisionbasics (the only account allowed).
  * At most one post per London calendar day, and a check against Instagram itself so a
    post that already went out is never sent twice.
  * A post is marked "published" in the queue only after Instagram confirms it.
  * Posts live in queue/*.json (posts.json, batch-2.json, ...). A new batch is a NEW file, so
    nothing that records what was already published is ever overwritten.
  * A term/id that was already published is never posted again: duplicates are skipped and reported.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))

QUEUE_DIR = ROOT / "queue"
QUEUE_PATH = QUEUE_DIR / "posts.json"
API_BASE = "https://graph.instagram.com/v25.0"
EXPECTED_USERNAME = "equivisionbasics"
LONDON = ZoneInfo("Europe/London")
POST_HOURS = range(8, 12)  # London hours (inclusive start, exclusive end) in which a scheduled run may post
SLIDE_TYPES = {"cover", "definition", "steps", "compare", "points", "recap"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,80}$")


class PublishError(Exception):
    pass


class IGError(PublishError):
    def __init__(self, message, code=None, subcode=None, status=None):
        super().__init__(message)
        self.code, self.subcode, self.status = code, subcode, status


# ------------------------------------------------------------------ small helpers
def log(msg=""):
    print(msg, flush=True)


def summary(md):
    """Append markdown to the GitHub job summary page (if running in Actions)."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(md + "\n")


def london_now():
    return datetime.now(LONDON)


def load_queue(path=QUEUE_PATH):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("posts"), list):
        raise PublishError('queue/posts.json must look like {"posts": [ ... ]}')
    return data


def save_queue(data, path=QUEUE_PATH):
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


class Queue:
    """Every queue/*.json file, treated as one long list of posts.

    Each post is written back to the file it came from, and a file is only rewritten if
    something in it changed. Files that cannot be read are reported in `.errors` and ignored.
    """

    def __init__(self, source=QUEUE_DIR):
        source = Path(source)
        paths = sorted(source.glob("*.json")) if source.is_dir() else [source]
        self.files, self.errors = [], []
        for path in paths:
            try:
                text = path.read_text(encoding="utf-8")
                data = json.loads(text)
                if not isinstance(data, dict) or not isinstance(data.get("posts"), list):
                    raise ValueError('must look like {"posts": [ ... ]}')
                for p in data["posts"]:
                    if not isinstance(p, dict):
                        raise ValueError("every post must be an object")
            except (OSError, ValueError) as e:
                self.errors.append(f"{path.name}: {e}")
                continue
            self.files.append((path, data, self._dump(data)))
        if not self.files and not self.errors:
            raise PublishError(f"no queue files found in {source}")

    @staticmethod
    def _dump(data):
        return json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    @property
    def data(self):
        return {"posts": [p for _, d, _ in self.files for p in d["posts"]]}

    def save(self, *_ignored):
        for i, (path, data, original) in enumerate(self.files):
            new = self._dump(data)
            if new != original:
                tmp = path.with_suffix(".tmp")
                tmp.write_text(new, encoding="utf-8")
                tmp.replace(path)
                self.files[i] = (path, data, new)


# ------------------------------------------------------------------ validation
def term_key(post):
    return re.sub(r"[^a-z0-9]+", "", str(post.get("term", "")).lower())


def caption_key(post):
    return _first_line(post.get("caption", "")).lower()


def validate_queue(posts):
    """Return a list of problems that involve more than one post (duplicates)."""
    problems = []
    for label, key in (("id", lambda p: p.get("id")), ("term", term_key), ("caption title", caption_key)):
        seen = {}
        for p in posts:
            k = key(p)
            if not k:
                continue
            if k in seen:
                problems.append(f"duplicate {label}: '{p.get('term')}' ({p.get('id')}) repeats {seen[k].get('id')}")
            else:
                seen[k] = p
    dates = {}
    for p in posts:
        if p.get("published") or p.get("skipped"):
            continue
        d = p.get("date")
        if d in dates:
            problems.append(f"two unpublished posts share the date {d}: {dates[d]} and {p.get('id')}")
        dates[d] = p.get("id")
    return problems


def duplicate_of(post, posts):
    """The already-published post this one repeats (same id, term or caption title), if any."""
    for other in posts:
        if other is post or not other.get("published"):
            continue
        if other.get("id") == post.get("id") or term_key(other) == term_key(post) or caption_key(other) == caption_key(post):
            return other
    return None


def validate_post(post):
    """Raise PublishError if the post could not be published as written."""
    problems = []
    for key in ("id", "date", "term", "caption", "slides"):
        if not post.get(key):
            problems.append(f"missing '{key}'")
    if problems:
        raise PublishError(f"post {post.get('id', '?')}: " + ", ".join(problems))
    if not ID_RE.match(post["id"]):
        problems.append("id must be lowercase letters, digits and dashes only")
    try:
        datetime.strptime(post["date"], "%Y-%m-%d")
    except ValueError:
        problems.append("date must look like 2026-09-20")
    n = len(post["slides"])
    if not 2 <= n <= 10:
        problems.append(f"needs 2-10 slides, has {n}")
    for i, s in enumerate(post["slides"], 1):
        if s.get("type") not in SLIDE_TYPES:
            problems.append(f"slide {i}: unknown type {s.get('type')!r}")
    cap = post["caption"]
    if len(cap) > 2200:
        problems.append(f"caption is {len(cap)} characters (limit 2,200)")
    if len(re.findall(r"#\w+", cap)) > 30:
        problems.append("caption has more than 30 hashtags")
    if problems:
        raise PublishError(f"post {post['id']}: " + "; ".join(problems))


# ------------------------------------------------------------------ Instagram API
class IG:
    """Tiny client for the Instagram API with Instagram Login (graph.instagram.com)."""

    def __init__(self, token, user_id, session=None, sleep=time.sleep, base=API_BASE,
                 poll_seconds=10, max_wait_seconds=300):
        self.token, self.user_id = token, str(user_id)
        self.s = session or requests.Session()
        self.sleep, self.base = sleep, base
        self.poll_seconds, self.max_wait = poll_seconds, max_wait_seconds

    def _call(self, method, path, params=None, data=None, retries=0):
        url = f"{self.base}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.token}"}
        attempt = 0
        while True:
            attempt += 1
            try:
                r = self.s.request(method, url, params=params, data=data, headers=headers, timeout=60)
            except requests.RequestException as e:
                if attempt <= retries:
                    self.sleep(5 * attempt)
                    continue
                raise IGError(f"network error talking to Instagram ({type(e).__name__})") from None
            try:
                body = r.json()
            except ValueError:
                body = {}
            if r.status_code >= 500 and attempt <= retries:
                self.sleep(5 * attempt)
                continue
            if r.status_code >= 400 or "error" in body:
                err = body.get("error", {}) if isinstance(body, dict) else {}
                msg = err.get("message") or f"HTTP {r.status_code}"
                raise IGError(f"Instagram API error: {msg}", err.get("code"), err.get("error_subcode"), r.status_code)
            return body

    # -- reads
    def me(self):
        return self._call("GET", "me", params={"fields": "user_id,username"}, retries=2)

    def recent_media(self, limit=10):
        body = self._call("GET", f"{self.user_id}/media",
                          params={"fields": "id,caption,timestamp,permalink", "limit": limit}, retries=2)
        return body.get("data", [])

    def permalink(self, media_id):
        return self._call("GET", str(media_id), params={"fields": "permalink"}, retries=2).get("permalink")

    def publishing_quota(self):
        body = self._call("GET", f"{self.user_id}/content_publishing_limit",
                          params={"fields": "quota_usage,config"}, retries=1)
        rows = body.get("data") or [{}]
        return rows[0].get("quota_usage"), (rows[0].get("config") or {}).get("quota_total")

    # -- writes (creating containers is safe to retry: unused containers just expire)
    def create_child(self, image_url):
        body = self._call("POST", f"{self.user_id}/media",
                          data={"image_url": image_url, "is_carousel_item": "true"}, retries=2)
        return body["id"]

    def create_carousel(self, child_ids, caption):
        body = self._call("POST", f"{self.user_id}/media",
                          data={"media_type": "CAROUSEL", "children": ",".join(child_ids), "caption": caption},
                          retries=2)
        return body["id"]

    def wait_finished(self, container_id, what="container"):
        waited = 0
        while True:
            body = self._call("GET", str(container_id), params={"fields": "status_code,status"}, retries=2)
            code = body.get("status_code")
            if code in ("FINISHED", "PUBLISHED"):
                return
            if code in ("ERROR", "EXPIRED"):
                raise IGError(f"{what} {code}: {body.get('status', 'no details given')}")
            if waited >= self.max_wait:
                raise IGError(f"{what} still {code} after {self.max_wait}s")
            self.sleep(self.poll_seconds)
            waited += self.poll_seconds

    def publish(self, creation_id):
        # never retried automatically: a retry after a lost reply could post twice
        body = self._call("POST", f"{self.user_id}/media_publish", data={"creation_id": creation_id}, retries=0)
        return body["id"]


# ------------------------------------------------------------------ image hosting (public 'media' branch)
def host_images(paths, post_id, repo, gh_token, run=subprocess.run, remote=None):
    """Push the JPEGs to an orphan 'media' branch and return their public raw URLs."""
    if not repo or not gh_token:
        raise PublishError("GITHUB_REPOSITORY / GITHUB_TOKEN missing - hosting only works inside GitHub Actions")
    if not ID_RE.match(post_id):
        raise PublishError(f"bad post id {post_id!r}")
    tmp = Path(tempfile.mkdtemp(prefix="media-"))
    try:
        dest = tmp / post_id
        dest.mkdir()
        for p in paths:
            shutil.copy(p, dest / Path(p).name)
        import base64
        auth = base64.b64encode(f"x-access-token:{gh_token}".encode()).decode()
        git = ["git", "-c", "user.name=equivision-bot", "-c", "user.email=equivision-bot@users.noreply.github.com"]

        def g(*args, extra=()):
            res = run([*git, *extra, *args], cwd=tmp, capture_output=True, text=True)
            if res.returncode != 0:
                # stderr may name the repo but never contains the token header
                raise PublishError(f"git {args[0]} failed: {res.stderr.strip()[:300]}")

        g("init", "-q", "-b", "media")
        g("add", "-A")
        g("commit", "-q", "-m", f"media for {post_id}")
        g("push", "-q", "--force", remote or f"https://github.com/{repo}.git", "media:media",
          extra=("-c", f"http.https://github.com/.extraheader=AUTHORIZATION: basic {auth}"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return [f"https://raw.githubusercontent.com/{repo}/media/{post_id}/{Path(p).name}" for p in paths]


def verify_urls(urls, session=None, sleep=time.sleep, tries=8):
    """Every URL must answer 200 with an image/jpeg content type before Instagram is asked to fetch it."""
    s = session or requests.Session()
    for url in urls:
        for attempt in range(1, tries + 1):
            try:
                r = s.get(url, timeout=30, stream=True)
                ok = r.status_code == 200 and r.headers.get("Content-Type", "").lower().startswith("image/jpeg")
                r.close()
            except requests.RequestException:
                ok = False
            if ok:
                break
            if attempt == tries:
                raise PublishError(f"image not publicly reachable as a JPEG: {url}")
            sleep(6)


# ------------------------------------------------------------------ duplicate guard
def _first_line(text):
    lines = (text or "").strip().splitlines()
    return lines[0].strip() if lines else ""


class DuplicateError(PublishError):
    """The post's term is already on Instagram (or already published from the queue)."""


def instagram_matches(ig, post, limit=30):
    """[(media, age_in_hours_or_None)] for recent Instagram posts whose caption title equals this post's."""
    want = caption_key(post)
    now = datetime.now(timezone.utc)
    found = []
    for m in ig.recent_media(limit):
        if _first_line(m.get("caption")).lower() != want:
            continue
        try:
            age = (now - datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")).total_seconds() / 3600
        except (KeyError, ValueError):
            age = None  # unknown time: treated as recent, the safe choice
        found.append((m, age))
    return found


def find_existing(ig, post, hours=48):
    """Return the Instagram media dict if this post already went out in the last `hours` hours."""
    for m, age in instagram_matches(ig, post, limit=10):
        if age is None or age <= hours:
            return m
    return None


# ------------------------------------------------------------------ choosing what to post
def select_post(posts, today, mode="scheduled"):
    """Return (post_or_None, reason). `today` is a YYYY-MM-DD string in London time."""
    approved = [p for p in posts if p.get("approved") and not p.get("published") and not p.get("skipped")]
    if mode == "publish_next":
        if not approved:
            return None, "no approved, unpublished posts left in the queue"
        return sorted(approved, key=lambda p: p["date"])[0], "next approved post"
    if any(p.get("published_date") == today for p in posts):
        return None, "a post has already gone out today"
    due = sorted((p for p in approved if p["date"] <= today), key=lambda p: p["date"])
    if due:
        return due[0], "due today" if due[0]["date"] == today else f"catching up (was dated {due[0]['date']})"
    if approved:
        return None, f"nothing due yet (next approved post is dated {min(p['date'] for p in approved)})"
    unapproved = [p for p in posts if not p.get("published") and not p.get("approved") and not p.get("skipped")]
    hint = f" ({len(unapproved)} waiting for approval)" if unapproved else ""
    raise PublishError("the queue has no approved posts left" + hint)


def mark_published(post, media_id, permalink, published_date=None):
    now = datetime.now(timezone.utc)
    post["published"] = True
    post["published_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    post["published_date"] = published_date or now.astimezone(LONDON).strftime("%Y-%m-%d")
    post["ig_media_id"] = media_id
    post["permalink"] = permalink


# ------------------------------------------------------------------ the publish flow
def render_default(post, out_dir):
    from render import render_post
    return render_post(post, out_dir)


def publish_post(post, ig, render=render_default, host=None, out_root=None, sleep=time.sleep, verify=verify_urls):
    """Render -> host -> Instagram containers -> publish. Returns (media_id, permalink, how)."""
    validate_post(post)
    matches = instagram_matches(ig, post)
    recent = [m for m, age in matches if age is None or age <= 48]
    if recent:
        log(f"Instagram already has this post ({recent[0].get('permalink')}). Not posting again.")
        return recent[0]["id"], recent[0].get("permalink"), "already-on-instagram"
    if matches:
        m, age = matches[0]
        raise DuplicateError(f"'{post['term']}' was already posted {age / 24:.0f} days ago ({m.get('permalink')})")

    out_dir = Path(out_root or ROOT / "out") / post["id"]
    log(f"Rendering {len(post['slides'])} slides ...")
    paths = render(post, out_dir)
    log("Uploading images ...")
    urls = host(paths, post["id"])
    verify(urls)

    log("Creating Instagram containers ...")
    children = [ig.create_child(u) for u in urls]
    for i, c in enumerate(children, 1):
        ig.wait_finished(c, f"slide {i}")
    carousel = ig.create_carousel(children, post["caption"])
    ig.wait_finished(carousel, "carousel")

    log("Publishing ...")
    try:
        media_id = ig.publish(carousel)
    except IGError as e:
        if e.status is not None and e.status < 500 and e.code is not None:
            raise  # Instagram clearly refused it: nothing was posted
        # unclear outcome (timeout / 5xx): look before deciding, never blind-retry
        sleep(30)
        existing = find_existing(ig, post)
        if not existing:
            raise
        return existing["id"], existing.get("permalink"), "published-after-timeout"
    return media_id, ig.permalink(media_id), "published"


def check_account(ig):
    me = ig.me()
    username = (me.get("username") or "").lower()
    if username != EXPECTED_USERNAME:
        raise PublishError(f"token belongs to @{username or '?'}, but only @{EXPECTED_USERNAME} is allowed. Stopping.")
    ids = {str(me.get("user_id")), str(me.get("id"))}
    if ig.user_id not in ids:
        raise PublishError("IG_USER_ID does not match the account this token belongs to")
    return username


# ------------------------------------------------------------------ modes
def run_check(data, ig, host, render=render_default, verify=verify_urls, file_errors=()):
    rows, failures = [], []
    username = check_account(ig)
    log(f"OK  token is valid and belongs to @{username}")
    rows.append(f"- Token valid, account **@{username}**")
    try:
        used, total = ig.publishing_quota()
        if used is not None:
            log(f"OK  publishing quota used in last 24h: {used}/{total}")
            rows.append(f"- Publishing quota: {used}/{total} used")
    except PublishError:
        pass

    for e in file_errors:
        failures.append(f"queue file cannot be read: {e}")
    posts = data["posts"]
    for p in posts:
        try:
            validate_post(p)
        except PublishError as e:
            failures.append(str(e))
    failures += validate_queue(posts)

    live = [p for p in posts if not p.get("published") and not p.get("skipped")]
    for p in live:
        d = duplicate_of(p, posts)
        if d:
            failures.append(f"'{p.get('term')}' ({p.get('id')}) repeats an already published post ({d.get('id')})")
    try:
        for p in live:
            for m, age in instagram_matches(ig, p):
                if age is not None and age > 48:
                    failures.append(f"'{p.get('term')}' is already on Instagram ({m.get('permalink')})")
    except PublishError as e:
        log(f"::warning::could not compare with Instagram's recent posts: {e}")

    ready = [p for p in live if p.get("approved")]
    waiting = [p for p in live if not p.get("approved")]
    done = sum(1 for p in posts if p.get("published"))
    log(f"     queue: {len(ready)} approved & waiting, {len(waiting)} not yet approved, {done} published")
    rows.append(f"- Queue: **{len(ready)}** approved and waiting, {len(waiting)} not yet approved, {done} already published")
    if ready:
        rows.append(f"- Approved posts cover **{min(p['date'] for p in ready)}** to **{max(p['date'] for p in ready)}**")

    if failures:
        for f in failures:
            log(f"BAD {f}")
        summary("### Check failed\n" + "\n".join(f"- {f}" for f in failures))
        raise PublishError(f"{len(failures)} problem(s) found in the queue (see above)")
    log("OK  no duplicate ids, terms or dates; every post is valid; nothing repeats what is already on Instagram")
    rows.append("- No duplicates, every post valid")

    nxt = sorted(ready or waiting, key=lambda p: p["date"])[:1]
    if nxt:
        post = nxt[0]
        out_dir = ROOT / "out" / "check"
        paths = render(post, out_dir)
        log(f"OK  rendered {len(paths)} slides of '{post['term']}'")
        urls = host([paths[0]], "check-image")
        verify(urls)
        log("OK  test image is publicly reachable as a JPEG (Instagram will be able to fetch images)")
        rows.append(f"- Rendered '{post['term']}' and confirmed image hosting works")
    log("\nCHECK PASSED - nothing was posted.")
    summary("### Check passed - nothing was posted\n" + "\n".join(rows))


def run_publish(data, ig, mode, today, enforce_window, host, dry_run=False, render=render_default,
                sleep=time.sleep, verify=verify_urls, save=save_queue, now=None):
    """Post at most one post. Posts that are duplicates or invalid are skipped (and reported at the end)
    so one bad entry can never block the days after it."""
    now = now or london_now()
    if enforce_window and now.hour not in POST_HOURS:
        log(f"London time is {now:%H:%M}; posts only go out between 08:00 and 11:59. Skipping this run.")
        return "skipped-window"
    posts = data["posts"]
    problems = []

    def skip(post, reason):
        post["skipped"] = reason
        problems.append(f"'{post.get('term')}' ({post.get('id')}) was skipped: {reason}")
        log(f"::warning::{problems[-1]}")
        if not dry_run:
            save(data)

    result = "nothing-due"
    for _ in range(len(posts) + 1):
        try:
            post, why = select_post(posts, today, mode)
        except PublishError as e:
            if not problems:
                raise
            log(f"Nothing left to post: {e}")
            break
        if not post:
            log(f"Nothing to post: {why}.")
            summary(f"Nothing to post: {why}.")
            break
        log(f"Selected '{post['term']}' ({post['id']}): {why}")
        try:
            validate_post(post)
        except PublishError as e:
            skip(post, f"invalid ({e})")
            continue
        dup = duplicate_of(post, posts)
        if dup:
            skip(post, f"duplicate of the already published post {dup.get('id')}")
            continue
        username = check_account(ig)
        log(f"Account check passed: @{username}")

        if dry_run:
            paths = render(post, ROOT / "out" / post["id"])
            log(f"Dry run: rendered {len(paths)} slides, nothing published.")
            result = "dry-run"
            break
        try:
            media_id, permalink, how = publish_post(post, ig, render=render, host=host, sleep=sleep, verify=verify)
        except DuplicateError as e:
            skip(post, f"already on Instagram - {e}")
            continue
        mark_published(post, media_id, permalink, published_date=today)
        save(data)
        log(f"DONE ({how}): {permalink}")
        summary(f"### Posted '{post['term']}'\n{permalink}")
        result = "published"
        break

    if result == "published":
        left = [p for p in posts if p.get("approved") and not p.get("published") and not p.get("skipped")]
        if len(left) < 3:
            msg = f"Only {len(left)} approved post(s) left in the queue. Add a new batch file to the queue folder soon."
            log(f"::warning::{msg}")
            summary(f"**{msg}**")
    if problems:
        summary("### Skipped posts\n" + "\n".join(f"- {x}" for x in problems))
        raise PublishError("; ".join(problems))
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["scheduled", "check", "publish_next"], default="scheduled")
    ap.add_argument("--enforce-window", action="store_true", help="only post between 08:00 and 11:59 London time")
    ap.add_argument("--dry-run", action="store_true", help="render only, publish nothing")
    ap.add_argument("--queue", default=str(QUEUE_DIR), help="queue folder (default) or a single queue file")
    args = ap.parse_args(argv)

    token, user_id = os.environ.get("IG_ACCESS_TOKEN"), os.environ.get("IG_USER_ID")
    if not token or not user_id:
        raise PublishError("secrets IG_ACCESS_TOKEN and IG_USER_ID are not set (Settings > Secrets and variables > Actions)")
    repo, gh_token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    ig = IG(token, user_id)
    queue = Queue(args.queue)
    for e in queue.errors:
        # an unreadable batch file must never stop the other files from being posted
        log(f"::warning::ignoring unreadable queue file {e}")
        summary(f"**Ignored unreadable queue file:** {e}")

    def host(paths, post_id):
        return host_images(paths, post_id, repo, gh_token)

    if args.mode == "check":
        run_check(queue.data, ig, host, file_errors=queue.errors)
        return 0
    today = london_now().strftime("%Y-%m-%d")
    run_publish(queue.data, ig, args.mode, today, args.enforce_window, host, dry_run=args.dry_run, save=queue.save)
    if queue.errors:
        raise PublishError("some queue files could not be read: " + "; ".join(queue.errors))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PublishError as e:
        log(f"::error::{e}")
        summary(f"### Failed\n{e}")
        sys.exit(1)
