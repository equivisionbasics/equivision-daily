# EquiVision Basics - daily Instagram poster

Every day at 08:00 London time, GitHub posts the next approved "finance term of the day"
carousel to **@equivisionbasics**. Nothing runs on your computer.

```
queue/posts.json         the posts (text, numbers, caption). One entry per day.
src/templates.py         the slide designs
src/render.py            turns a post into 6 JPEG slides (1080x1350)
src/publish.py           uploads and publishes to Instagram, with safety checks
src/refresh_token.py     keeps the Instagram token alive (weekly)
.github/workflows/       the two schedules
tests/                   offline tests (no Instagram needed)
```

## One-time setup

1. **Create the repository.** On github.com: **+ > New repository**. Name it `equivision-daily`,
   choose **Public** (Instagram must be able to download the slide images; the slides contain
   nothing private), tick **Add a README**, click **Create repository**.
2. **Upload the files.** In the repo click **Add file > Upload files** and drag in everything from
   the `equivision-daily` folder *except* the hidden `.github` folder: `assets`, `queue`, `src`,
   `tests`, `requirements.txt`, `.gitignore`. Click **Commit changes**.
3. **Add the two workflow files** (they live in a hidden folder, so create them by hand):
   **Add file > Create new file**, type `.github/workflows/daily-post.yml` as the name (typing the
   slashes creates the folders), paste in the contents of `daily-post.yml`, **Commit changes**.
   Repeat for `.github/workflows/refresh-token.yml`.
4. **Add the secrets.** **Settings > Secrets and variables > Actions > New repository secret**:
   - `IG_ACCESS_TOKEN` : the token from the Meta dashboard
   - `IG_USER_ID` : `17841480490372025`
5. **Run the safe test.** **Actions > Daily Instagram post > Run workflow**, mode **check**.
   It verifies the token, confirms the account is `@equivisionbasics`, validates every post,
   renders one, and proves Instagram will be able to download the images. It posts nothing.
   Green tick = ready.
6. **Approve posts.** Only posts with `"approved": true` are ever published.
7. (Optional, recommended) **Token auto-update.** Create a fine-grained personal access token
   (github.com > Settings > Developer settings > Fine-grained tokens) for this repository only,
   permission **Secrets: Read and write**, and save it as the secret `GH_PAT`. It is only used
   if Instagram ever returns a new token string when refreshing.

## Every day

Nothing. At 08:00 London time the workflow posts the earliest approved post that is due, marks
it `"published": true` in `queue/posts.json`, and commits that change. You get a GitHub email
if a run fails. The run page shows a link to the live post.

If a day is missed, the next run posts the overdue one, so no post is skipped.

## Adding more posts

Add entries to the `posts` list in `queue/posts.json` (same shape as the existing ones), each
with a unique `id`, a `date`, and `"approved": false`. Preview by running
`python src/render.py queue/posts.json out 0` (the last number is the post's position). When you
are happy, set `"approved": true`. The run warns you when fewer than 3 approved posts remain.

Slide types: `cover`, `definition`, `steps`, `compare`, `points`, `recap`.
In text, `[[word]]` highlights in light blue and `**word**` is bold.

## Good to know

- **Token:** lasts 60 days, refreshed every Monday by `refresh-token.yml`. If it ever fails,
  generate a new token in the Meta dashboard and replace the `IG_ACCESS_TOKEN` secret.
- **Pauses:** GitHub pauses scheduled workflows in a repository with no activity for 60 days.
  Each daily post commits the queue, and adding new posts counts as activity, so this only
  matters if the queue runs dry. If it happens, click **Enable workflow** on the Actions tab.
- **Limits:** Instagram allows 100 API posts per day and 10 slides per carousel. This uses 1 post
  and 6 slides per day.
- **Safety:** the publisher stops if the token does not belong to `@equivisionbasics`, never posts
  twice in a day, and asks Instagram whether the post already exists before sending it.
- **Manual post now:** Actions > Daily Instagram post > Run workflow > mode `publish_next`.

## Running the tests locally (optional)

```
pip install -r requirements.txt pytest
python -m playwright install chromium
python -m pytest tests -q
```
