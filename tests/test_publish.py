"""Offline tests: a fake Instagram API stands in for the real one. Run:  python -m pytest tests -q"""
import copy
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import publish as P  # noqa: E402
import refresh_token as RT  # noqa: E402

CAPTION = "Inflation, explained simply \U0001F447\n\nPrices rise.\n\n#finance #inflation"
POST = {"id": "2026-09-20-inflation", "date": "2026-09-20", "term": "Inflation", "caption": CAPTION,
        "slides": [{"type": "cover", "term": "Inflation"}] + [{"type": "recap", "title": "x"}] * 5,
        "approved": True, "published": False}


class Resp:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body if body is not None else {}, headers or {}

    def json(self):
        return self._body

    def close(self):
        pass


class FakeIG:
    """Behaves like graph.instagram.com for the calls we make."""

    def __init__(self, username="equivisionbasics", uid="17841480490372025"):
        self.username, self.uid = username, uid
        self.calls, self.media, self.n = [], [], 0
        self.status_seq = {}          # container id -> list of status codes to return
        self.fail_publish = None      # Resp to return from media_publish
        self.publish_lands_but_times_out = False
        self.headers_seen = set()

    def request(self, method, url, params=None, data=None, headers=None, timeout=None):
        self.headers_seen.add((headers or {}).get("Authorization"))
        path = url.split("/v25.0/")[1]
        self.calls.append((method, path, dict(params or {}), dict(data or {})))
        if path == "me":
            return Resp(body={"user_id": self.uid, "id": "999", "username": self.username})
        if path == f"{self.uid}/media" and method == "GET":
            return Resp(body={"data": list(self.media)})
        if path == f"{self.uid}/media" and method == "POST":
            self.n += 1
            return Resp(body={"id": f"c{self.n}"})
        if path == f"{self.uid}/media_publish":
            if self.publish_lands_but_times_out:
                self.media.append({"id": "m1", "caption": self.caption, "timestamp": _ts(0), "permalink": "https://ig/p/1"})
                raise requests.ConnectionError("boom")
            if self.fail_publish:
                return self.fail_publish
            return Resp(body={"id": "m1"})
        if path == "m1":
            return Resp(body={"permalink": "https://ig/p/1"})
        if path.startswith("c"):
            seq = self.status_seq.get(path)
            code = seq.pop(0) if seq else "FINISHED"
            return Resp(body={"status_code": code, "status": f"{code} detail"})
        return Resp(404, {"error": {"message": "unknown " + path}})


def _ts(hours_ago):
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%S+0000")


def fake_render(post, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(1, len(post["slides"]) + 1):
        p = out_dir / f"slide_{i}.jpg"
        Image.new("RGB", (8, 10), "white").save(p, "JPEG")
        paths.append(p)
    return paths


def make_ig(fake):
    return P.IG("SECRET_TOKEN", fake.uid, session=fake, sleep=lambda s: None, poll_seconds=1, max_wait_seconds=5)


def host_ok(paths, post_id):
    return [f"https://raw.example/{post_id}/{p.name}" for p in paths]


def noverify(urls):
    return None


@pytest.fixture
def env(tmp_path):
    data = {"posts": [copy.deepcopy(POST)]}
    q = tmp_path / "posts.json"
    q.write_text(json.dumps(data))
    fake = FakeIG()
    fake.caption = CAPTION
    return data, q, fake


def run(data, q, fake, mode="scheduled", today="2026-09-20", window=False, now=None, **kw):
    return P.run_publish(data, make_ig(fake), mode, today, window, host_ok, render=fake_render,
                         sleep=lambda s: None, verify=noverify, save=lambda d: P.save_queue(d, q),
                         now=now or datetime(2026, 9, 20, 8, 5, tzinfo=P.LONDON), **kw)


def test_happy_path_posts_carousel_and_marks_published(env, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "ROOT", tmp_path)
    data, q, fake = env
    assert run(data, q, fake) == "published"
    posts = [c for c in fake.calls if c[0] == "POST"]
    kids = [c for c in posts if c[3].get("is_carousel_item") == "true"]
    assert len(kids) == 6 and all(c[3]["image_url"].startswith("https://raw.example/") for c in kids)
    car = [c for c in posts if c[3].get("media_type") == "CAROUSEL"][0]
    assert car[3]["children"] == "c1,c2,c3,c4,c5,c6" and car[3]["caption"] == CAPTION
    pub = [c for c in posts if c[1].endswith("media_publish")]
    assert len(pub) == 1 and pub[0][3]["creation_id"] == "c7"
    saved = json.loads(q.read_text())["posts"][0]
    assert saved["published"] and saved["ig_media_id"] == "m1" and saved["permalink"] == "https://ig/p/1"
    assert saved["published_date"]
    assert fake.headers_seen == {"Bearer SECRET_TOKEN"}  # token only in the header


def test_second_run_same_day_does_nothing(env, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "ROOT", tmp_path)
    data, q, fake = env
    run(data, q, fake)
    before = len(fake.calls)
    today = data["posts"][0]["published_date"]
    data["posts"].append({**copy.deepcopy(POST), "id": "2026-09-21-stocks", "date": "2026-09-20", "caption": "Stocks, x"})
    assert run(data, q, fake, today=today) == "nothing-due"
    assert len(fake.calls) == before


def test_unapproved_post_is_never_published(env):
    data, q, fake = env
    data["posts"][0]["approved"] = False
    with pytest.raises(P.PublishError, match="no approved posts"):
        run(data, q, fake)
    assert not any(c[0] == "POST" for c in fake.calls)


def test_future_post_waits(env):
    data, q, fake = env
    assert run(data, q, fake, today="2026-09-19") == "nothing-due"
    assert fake.calls == []


def test_overdue_post_is_caught_up(env, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "ROOT", tmp_path)
    data, q, fake = env
    assert run(data, q, fake, today="2026-09-22") == "published"


def test_wrong_account_is_refused(env):
    data, q, fake = env
    fake.username = "someone_else"
    with pytest.raises(P.PublishError, match="only @equivisionbasics"):
        run(data, q, fake)
    assert not any(c[0] == "POST" for c in fake.calls)


def test_wrong_user_id_is_refused(env):
    data, q, fake = env
    fake.uid = "1"
    ig = P.IG("t", "2", session=fake, sleep=lambda s: None)
    fake.uid = "1"
    with pytest.raises(P.PublishError, match="IG_USER_ID"):
        P.check_account(ig)


def test_duplicate_on_instagram_is_not_reposted(env):
    data, q, fake = env
    fake.media = [{"id": "m0", "caption": CAPTION, "timestamp": _ts(2), "permalink": "https://ig/p/0"}]
    assert run(data, q, fake) == "published"
    assert not any(c[0] == "POST" for c in fake.calls)
    saved = json.loads(q.read_text())["posts"][0]
    assert saved["published"] and saved["ig_media_id"] == "m0"


def test_old_post_with_same_title_does_not_block(env, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "ROOT", tmp_path)
    data, q, fake = env
    fake.media = [{"id": "m0", "caption": CAPTION, "timestamp": _ts(24 * 30), "permalink": "x"}]
    assert run(data, q, fake) == "published"


def test_outside_window_skips_when_enforced(env):
    data, q, fake = env
    now = datetime(2026, 9, 20, 6, 0, tzinfo=P.LONDON)
    assert run(data, q, fake, window=True, now=now) == "skipped-window"
    assert fake.calls == []


def test_window_open_at_nine(env, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "ROOT", tmp_path)
    data, q, fake = env
    now = datetime(2026, 9, 20, 9, 30, tzinfo=P.LONDON)
    assert run(data, q, fake, window=True, now=now) == "published"


def test_container_error_stops_and_does_not_mark(env, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "ROOT", tmp_path)
    data, q, fake = env
    fake.status_seq["c3"] = ["IN_PROGRESS", "ERROR"]
    with pytest.raises(P.IGError, match="slide 3 ERROR"):
        run(data, q, fake)
    assert not json.loads(q.read_text())["posts"][0]["published"]
    assert not any(c[1].endswith("media_publish") for c in fake.calls)


def test_stuck_container_times_out(env, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "ROOT", tmp_path)
    data, q, fake = env
    fake.status_seq["c2"] = ["IN_PROGRESS"] * 50
    with pytest.raises(P.IGError, match="still IN_PROGRESS"):
        run(data, q, fake)


def test_publish_refused_by_instagram_is_an_error(env, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "ROOT", tmp_path)
    data, q, fake = env
    fake.fail_publish = Resp(400, {"error": {"message": "Media ID is not available", "code": 9007}})
    with pytest.raises(P.IGError, match="not available"):
        run(data, q, fake)
    assert not json.loads(q.read_text())["posts"][0]["published"]


def test_lost_reply_after_publish_is_detected_not_retried(env, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "ROOT", tmp_path)
    data, q, fake = env
    fake.publish_lands_but_times_out = True
    assert run(data, q, fake) == "published"
    assert len([c for c in fake.calls if c[1].endswith("media_publish")]) == 1
    assert json.loads(q.read_text())["posts"][0]["ig_media_id"] == "m1"


def test_dry_run_publishes_nothing(env, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "ROOT", tmp_path)
    data, q, fake = env
    assert run(data, q, fake, dry_run=True) == "dry-run"
    assert not any(c[0] == "POST" for c in fake.calls)


def test_publish_next_ignores_date(env, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "ROOT", tmp_path)
    data, q, fake = env
    assert run(data, q, fake, mode="publish_next", today="2026-01-01") == "published"


@pytest.mark.parametrize("mut,msg", [
    (lambda p: p.update(caption="x" * 2201), "2,200"),
    (lambda p: p.update(caption="#a " * 31), "30 hashtags"),
    (lambda p: p.update(slides=[POST["slides"][0]]), "2-10 slides"),
    (lambda p: p.update(slides=[POST["slides"][0]] * 11), "2-10 slides"),
    (lambda p: p.update(id="Bad Id"), "id must be"),
    (lambda p: p.update(date="20/09/2026"), "date must"),
    (lambda p: p["slides"].__setitem__(0, {"type": "nope"}), "unknown type"),
])
def test_validation(mut, msg):
    p = copy.deepcopy(POST)
    mut(p)
    with pytest.raises(P.PublishError, match=msg):
        P.validate_post(p)


def test_check_mode_posts_nothing(env, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "ROOT", tmp_path)
    data, q, fake = env
    P.run_check(data, make_ig(fake), host_ok, render=fake_render, verify=noverify)
    assert not any(c[0] == "POST" for c in fake.calls)


def test_runway_warning(env, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(P, "ROOT", tmp_path)
    data, q, fake = env
    run(data, q, fake)
    assert "::warning::Only 0 approved post(s) left" in capsys.readouterr().out


def test_verify_urls_rejects_non_jpeg():
    class S:
        def get(self, url, **kw):
            return Resp(200, headers={"Content-Type": "text/plain"})
    with pytest.raises(P.PublishError, match="not publicly reachable"):
        P.verify_urls(["https://x/y.jpg"], session=S(), sleep=lambda s: None, tries=2)


def test_verify_urls_accepts_jpeg():
    class S:
        def get(self, url, **kw):
            return Resp(200, headers={"Content-Type": "image/jpeg"})
    P.verify_urls(["https://x/y.jpg"], session=S(), sleep=lambda s: None)


# ---------------------------------------------------------------- token refresh
class RefreshSession:
    def __init__(self, resp):
        self.resp = resp

    def get(self, url, params=None, timeout=None):
        assert params["grant_type"] == "ig_refresh_token"
        return self.resp


def test_refresh_same_token_is_fine(capsys):
    s = RefreshSession(Resp(200, {"access_token": "T", "expires_in": 5184000}))
    assert RT.main({"IG_ACCESS_TOKEN": "T"}, s) == 0
    assert "Same token string" in capsys.readouterr().out


def test_refresh_new_token_updates_secret():
    s = RefreshSession(Resp(200, {"access_token": "NEW", "expires_in": 5184000}))
    seen = {}

    def fake_run(cmd, input, text, capture_output, env):
        seen.update(cmd=cmd, input=input, pat=env["GH_TOKEN"])
        return type("R", (), {"returncode": 0, "stderr": ""})()
    assert RT.main({"IG_ACCESS_TOKEN": "OLD", "GH_PAT": "pat", "GITHUB_REPOSITORY": "a/b"}, s, fake_run) == 0
    assert seen["input"] == "NEW" and seen["pat"] == "pat" and "IG_ACCESS_TOKEN" in seen["cmd"]


def test_refresh_new_token_without_pat_fails_loudly(capsys):
    s = RefreshSession(Resp(200, {"access_token": "NEW", "expires_in": 5184000}))
    assert RT.main({"IG_ACCESS_TOKEN": "OLD"}, s) == 1
    assert "GH_PAT" in capsys.readouterr().out


def test_refresh_too_young_token_is_not_a_failure():
    s = RefreshSession(Resp(400, {"error": {"message": "Token must be at least 24 hours old"}}))
    assert RT.main({"IG_ACCESS_TOKEN": "T"}, s) == 0


def test_refresh_expired_token_fails():
    s = RefreshSession(Resp(400, {"error": {"message": "Session has expired"}}))
    assert RT.main({"IG_ACCESS_TOKEN": "T"}, s) == 1


# ---------------------------------------------------------------- the real queue
def test_shipped_queue_is_valid():
    data = P.load_queue(ROOT / "queue" / "posts.json")
    ids = set()
    for p in data["posts"]:
        P.validate_post(p)
        assert p["id"] not in ids
        ids.add(p["id"])
        assert p["published"] is False


# ---------------------------------------------------------------- image hosting + real rendering
def test_host_images_pushes_to_media_branch(tmp_path):
    import subprocess
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    imgs = fake_render({"slides": [1, 2, 3]}, tmp_path / "imgs")
    urls = P.host_images(imgs, "2026-09-20-inflation", "owner/repo", "tok", remote=str(bare))
    assert urls[0] == "https://raw.githubusercontent.com/owner/repo/media/2026-09-20-inflation/slide_1.jpg"
    files = subprocess.run(["git", "--git-dir", str(bare), "ls-tree", "-r", "--name-only", "media"],
                           capture_output=True, text=True, check=True).stdout.split()
    assert files == [f"2026-09-20-inflation/slide_{i}.jpg" for i in (1, 2, 3)]
    # a second post replaces the first (force push), so the branch never grows
    P.host_images(imgs, "2026-09-21-stocks", "owner/repo", "tok", remote=str(bare))
    files = subprocess.run(["git", "--git-dir", str(bare), "ls-tree", "-r", "--name-only", "media"],
                           capture_output=True, text=True, check=True).stdout.split()
    assert all(f.startswith("2026-09-21-stocks/") for f in files)


def test_real_render_meets_instagram_image_rules(tmp_path):
    from render import render_post
    post = P.load_queue(ROOT / "queue" / "posts.json")["posts"][0]
    paths = render_post(post, tmp_path)
    assert len(paths) == 6
    for p in paths:
        assert p.read_bytes()[:3] == b"\xff\xd8\xff"          # JPEG
        assert p.stat().st_size < 8 * 1024 * 1024               # Instagram limit is 8 MB
        with Image.open(p) as im:
            assert im.format == "JPEG" and im.mode == "RGB" and im.size == (1080, 1350)  # 4:5, inside 4:5..1.91:1
