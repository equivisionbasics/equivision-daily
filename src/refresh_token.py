#!/usr/bin/env python3
"""Refresh the long-lived Instagram token so it never expires (run weekly by GitHub Actions).

A long-lived token lasts 60 days and can be refreshed once it is at least 24 hours old.
If Instagram hands back a different token string, the GitHub secret IG_ACCESS_TOKEN is
updated automatically (needs the GH_PAT secret). If the string is unchanged, nothing else
needs doing - the 60-day clock has simply been restarted.
"""
import os
import subprocess
import sys

import requests

REFRESH_URL = "https://graph.instagram.com/refresh_access_token"


def refresh(token, session=None):
    s = session or requests.Session()
    try:
        r = s.get(REFRESH_URL, params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=60)
    except requests.RequestException as e:
        raise SystemExit(f"::error::network error while refreshing ({type(e).__name__})")
    try:
        body = r.json()
    except ValueError:
        body = {}
    if r.status_code >= 400 or "error" in body:
        msg = (body.get("error") or {}).get("message") or f"HTTP {r.status_code}"
        return None, msg
    return body, None


def set_secret(new_token, pat, repo, run=subprocess.run):
    res = run(["gh", "secret", "set", "IG_ACCESS_TOKEN", "--repo", repo],
              input=new_token, text=True, capture_output=True, env={**os.environ, "GH_TOKEN": pat})
    if res.returncode != 0:
        raise SystemExit(f"::error::could not update the IG_ACCESS_TOKEN secret: {res.stderr.strip()[:200]}")


def main(env=os.environ, session=None, run=subprocess.run):
    token = env.get("IG_ACCESS_TOKEN")
    if not token:
        raise SystemExit("::error::IG_ACCESS_TOKEN secret is not set")
    body, err = refresh(token, session)
    if err:
        if "24 hours" in err:
            print(f"::notice::Token is less than 24 hours old, so it cannot be refreshed yet. That is fine. ({err})")
            return 0
        print(f"::error::Token refresh failed: {err}")
        print("If the token has expired, generate a new one in the Meta app dashboard "
              "(Instagram > API setup with Instagram login) and update the IG_ACCESS_TOKEN secret.")
        return 1
    new = body.get("access_token")
    days = int(body.get("expires_in", 0)) // 86400
    if not new:
        print("::error::Instagram answered without a token")
        return 1
    if new == token:
        print(f"Token refreshed. Same token string, now valid for about {days} more days. Nothing to update.")
        return 0
    pat, repo = env.get("GH_PAT"), env.get("GITHUB_REPOSITORY")
    if not pat:
        print("::error::Instagram issued a NEW token string but the GH_PAT secret is missing, so the "
              "IG_ACCESS_TOKEN secret was not updated. Add GH_PAT (see README, step 8) and re-run.")
        return 1
    set_secret(new, pat, repo, run)
    print(f"Token refreshed and the IG_ACCESS_TOKEN secret updated. Valid for about {days} more days.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
