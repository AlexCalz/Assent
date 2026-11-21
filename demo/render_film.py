"""Render the Assent film frame-by-frame.

The page exposes window.__seek(t), which pauses every animation and sets its
currentTime to an absolute position. So each frame is a pure function of time —
no dropped frames, no real-time capture jitter, full 1080p.
"""

import os
import pathlib
import shutil
import time

from playwright.sync_api import sync_playwright

# The film (demo/film.html) exposes window.__seek(t): it pauses every animation and
# sets its currentTime to an absolute position, so each frame is a pure function of
# time. That is why this renders frame-exactly instead of screen-capturing in real time.
#
#   pip install playwright && playwright install chromium
#   python demo/render_film.py
#   ffmpeg -framerate 30 -i out/frames/f%05d.jpg -c:v libx264 -preset slow -crf 19 \
#          -pix_fmt yuv420p -movflags +faststart assent-film.mp4

REPO = pathlib.Path(__file__).resolve().parent.parent
SC = pathlib.Path(os.environ.get("ASSENT_OUT", REPO / "demo" / "out"))
SOURCE = REPO / "demo" / "film.html"
FRAMES = SC / "frames"
CHROME = os.environ.get("ASSENT_CHROME")  # None => Playwright's bundled Chromium
FPS = 30
DURATION = 38.5
W, H = 1920, 1080


def main():
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True)

    total = int(DURATION * FPS)
    t0 = time.time()

    with sync_playwright() as p:
        launch = {"args": ["--force-color-profile=srgb", "--font-render-hinting=none",
                           "--disable-lcd-text", "--hide-scrollbars"]}
        if CHROME:
            launch["executable_path"] = CHROME
        b = p.chromium.launch(**launch)
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        pg.goto(SOURCE.resolve().as_uri())
        pg.wait_for_function("window.__ready===true")
        pg.wait_for_timeout(900)  # let fonts settle

        for i in range(total):
            t = i / FPS
            pg.evaluate("t => window.__seek(t)", t)
            pg.screenshot(
                path=str(FRAMES / f"f{i:05d}.jpg"), type="jpeg", quality=94
            )
            if i % 120 == 0:
                el = time.time() - t0
                print(f"  {i}/{total}  {el:.0f}s elapsed", flush=True)

        b.close()

    print(f"done: {total} frames in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
