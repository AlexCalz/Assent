"""Record a screen-capture demo of the Assent control plane.

    pip install playwright && playwright install chromium
    python demo/record_demo.py

Drives the real app in Chromium via Playwright and records video. Nothing is faked:
every click hits the running server and moves a change through the real policy engine,
so the ledger shown at the end is the genuine record of the demo you just watched.

Produces a .webm; convert with:
    ffmpeg -i video/*.webm -vf "scale=1280:-2,fps=24" -c:v libx264 -crf 23 \
           -pix_fmt yuv420p -movflags +faststart assent-demo.mp4

Set ASSENT_CHROME to use a specific Chromium binary (otherwise Playwright's own).
"""

import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROME = os.environ.get("ASSENT_CHROME")  # None => Playwright's bundled Chromium
OUT = Path(os.environ.get("ASSENT_DEMO_OUT", "video"))
PORT = int(os.environ.get("ASSENT_DEMO_PORT", "8412"))
W, H = 1280, 860

# A soft pointer overlay + a caption bar, injected so the recording is legible.
OVERLAY = """
(() => {
  const boot = () => {
    if (document.getElementById('__cur')) return;
    const c = document.createElement('div');
    c.id = '__cur';
    c.style.cssText = `position:fixed;z-index:2147483647;width:22px;height:22px;
      border-radius:50%;background:rgba(79,91,213,.35);border:2px solid #4f5bd5;
      left:-50px;top:-50px;pointer-events:none;
      transition:left .55s cubic-bezier(.4,0,.2,1),top .55s cubic-bezier(.4,0,.2,1),
      transform .18s ease, background .18s ease;`;
    document.body.appendChild(c);

    const cap = document.createElement('div');
    cap.id = '__cap';
    cap.style.cssText = `position:fixed;z-index:2147483646;left:50%;bottom:26px;
      transform:translateX(-50%) translateY(14px);opacity:0;
      background:rgba(16,18,26,.93);color:#fff;font:600 16px/1.45 ui-sans-serif,system-ui,sans-serif;
      padding:12px 22px;border-radius:11px;max-width:80vw;text-align:center;
      box-shadow:0 10px 40px rgba(0,0,0,.4);pointer-events:none;
      transition:opacity .35s ease, transform .35s ease;`;
    document.body.appendChild(cap);

    window.__cursor = (x, y) => {
      const e = document.getElementById('__cur');
      e.style.left = (x - 11) + 'px'; e.style.top = (y - 11) + 'px';
    };
    window.__press = () => {
      const e = document.getElementById('__cur');
      e.style.transform = 'scale(.65)'; e.style.background = 'rgba(79,91,213,.75)';
      setTimeout(() => { e.style.transform = 'scale(1)'; e.style.background = 'rgba(79,91,213,.35)'; }, 220);
    };
    window.__say = (t) => {
      const e = document.getElementById('__cap');
      if (!t) { e.style.opacity = '0'; e.style.transform = 'translateX(-50%) translateY(14px)'; return; }
      e.textContent = t; e.style.opacity = '1'; e.style.transform = 'translateX(-50%) translateY(0)';
    };
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
"""


def say(page, text, hold=2.6):
    page.evaluate("t => window.__say && window.__say(t)", text)
    time.sleep(hold)


def clear(page):
    page.evaluate("() => window.__say && window.__say('')")
    time.sleep(0.4)


def glide_click(page, locator, pause=1.1):
    """Move the pointer overlay to the element, then really click it."""
    locator.scroll_into_view_if_needed()
    time.sleep(0.6)
    box = locator.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.evaluate("([x,y]) => window.__cursor && window.__cursor(x,y)", [x, y])
    time.sleep(0.8)
    page.evaluate("() => window.__press && window.__press()")
    time.sleep(0.3)
    locator.click()
    time.sleep(pause)


def smooth_scroll(page, total, steps=18, per=0.045):
    step = total / steps
    for _ in range(steps):
        page.mouse.wheel(0, step)
        time.sleep(per)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).resolve().parent.parent
    server = subprocess.Popen(
        [sys.executable, "-m", "assent.app", "--port", str(PORT), "--actor", "alex"],
        cwd=str(repo_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2.0)
    base = f"http://127.0.0.1:{PORT}"

    try:
        with sync_playwright() as p:
            launch_args = {"args": ["--force-color-profile=srgb"]}
            if CHROME:
                launch_args["executable_path"] = CHROME
            browser = p.chromium.launch(**launch_args)
            ctx = browser.new_context(
                viewport={"width": W, "height": H},
                record_video_dir=str(OUT),
                record_video_size={"width": W, "height": H},
                device_scale_factor=1,
                color_scheme="light",
            )
            page = ctx.new_page()
            page.add_init_script(OVERLAY)

            # --- title card -------------------------------------------------
            page.goto(base)
            page.evaluate("""() => {
              const o = document.createElement('div');
              o.id='__title';
              o.style.cssText=`position:fixed;inset:0;z-index:2147483645;background:#12141b;
                display:flex;flex-direction:column;align-items:center;justify-content:center;
                color:#fff;font-family:ui-sans-serif,system-ui,sans-serif;gap:14px;`;
              o.innerHTML = `<div style="display:flex;align-items:center;gap:12px">
                  <span style="width:14px;height:14px;border-radius:50%;background:#8b93f0;
                    box-shadow:0 0 0 6px rgba(139,147,240,.18)"></span>
                  <span style="font-size:30px;font-weight:750;letter-spacing:-.02em">Assent</span>
                </div>
                <div style="font-size:19px;color:#a6aec0;max-width:640px;text-align:center;line-height:1.5">
                  The control plane that lets AI security agents act &mdash; safely.</div>
                <div style="font-size:14px;color:#6b7488;margin-top:6px">live product demo</div>`;
              document.body.appendChild(o);
            }""")
            time.sleep(3.2)
            page.evaluate("""() => { const t=document.getElementById('__title');
              t.style.transition='opacity .6s ease'; t.style.opacity='0';
              setTimeout(()=>t.remove(), 650); }""")
            time.sleep(1.0)

            # --- the queue --------------------------------------------------
            say(page, "Five detections came in. Assent decided what to do with each one.", 3.4)
            clear(page)
            say(page, "Two were safe enough to handle automatically. Three need a human.", 3.4)
            clear(page)

            smooth_scroll(page, 420)
            time.sleep(0.8)
            say(page, "A leaked production credential — Assent refused to act on its own.", 3.4)
            clear(page)

            smooth_scroll(page, 300)
            time.sleep(0.6)
            say(page, "A second AI reviewed it independently and dissented. That alone escalates it.", 4.0)
            clear(page)
            say(page, "Every decision shows exactly why it was made.", 3.0)
            clear(page)

            # --- approve ----------------------------------------------------
            card = page.locator('article.card:has(.rec-id:text-is("chg-0002"))')
            approve = card.locator('form[action="/approve"] button')
            say(page, "As the owner, I approve it.", 2.2)
            glide_click(page, approve, pause=1.6)
            clear(page)

            say(page, "Approved, executed, and logged — and Assent just learned who owns that system.", 4.2)
            clear(page)

            # --- undo -------------------------------------------------------
            smooth_scroll(page, 900)
            time.sleep(0.8)
            say(page, "Anything it did on its own can be undone in one click.", 3.2)
            clear(page)

            undo = page.locator('article.card:has(.rec-id:text-is("chg-0001")) form[action="/rollback"] button')
            glide_click(page, undo, pause=1.8)
            say(page, "Rolled back.", 2.2)
            clear(page)

            # --- ledger -----------------------------------------------------
            page.evaluate("() => window.scrollTo({top:0, behavior:'smooth'})")
            time.sleep(1.0)
            say(page, "And every step is recorded in a tamper-proof ledger.", 3.0)
            clear(page)
            glide_click(page, page.locator('nav a[href="/ledger"]'), pause=1.6)

            say(page, "Proposed, decided, approved, executed, rolled back — with who and when.", 4.2)
            clear(page)
            smooth_scroll(page, 260)
            time.sleep(0.7)
            say(page, "Change any past entry and the chain breaks. Accountability you can verify.", 4.2)
            clear(page)
            page.evaluate("() => window.scrollTo({top:0, behavior:'smooth'})")
            time.sleep(1.4)

            # --- outro ------------------------------------------------------
            say(page, "Nothing acts without assent.", 3.4)
            time.sleep(1.0)

            path = page.video.path()
            ctx.close()
            browser.close()
            print("raw video:", path)
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    main()
