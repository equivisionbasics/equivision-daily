"""Render a post (list of slide dicts) to 1080x1350 JPEG files with Playwright + Pillow."""
import base64
import io
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from templates import build_slide_html  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def _ctx():
    logo = "data:image/png;base64," + base64.b64encode((ASSETS / "logo.png").read_bytes()).decode()
    return {"logo": logo, "fonts": (ASSETS / "fonts").resolve().as_uri()}


def render_post(post, out_dir, jpeg_quality=92):
    """Returns the list of JPEG paths (slide_1.jpg ...) in order."""
    from playwright.sync_api import sync_playwright

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    slides = post["slides"]
    total = len(slides)
    ctx = _ctx()
    paths = []
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        for i, slide in enumerate(slides, 1):
            html_path = Path(tmp) / f"slide_{i}.html"
            html_path.write_text(build_slide_html(slide, i, total, ctx), encoding="utf-8")
            page.goto(html_path.as_uri())
            page.wait_for_selector("body[data-ready='1']", timeout=15000)
            png = page.screenshot(type="png")
            img = Image.open(io.BytesIO(png)).convert("RGB")
            assert img.size == (1080, 1350), img.size
            dest = out_dir / f"slide_{i}.jpg"
            img.save(dest, "JPEG", quality=jpeg_quality, optimize=True, subsampling=0)
            paths.append(dest)
        browser.close()
    return paths


if __name__ == "__main__":
    import json

    src = Path(sys.argv[1])
    data = json.loads(src.read_text())
    post = data["posts"][int(sys.argv[3])] if isinstance(data, dict) and "posts" in data else data
    files = render_post(post, sys.argv[2])
    print("\n".join(str(f) for f in files))
