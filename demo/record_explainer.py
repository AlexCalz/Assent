"""Record a captioned walkthrough of docs/how-it-works.html, and export it as a PDF.

    pip install playwright && playwright install chromium
    python demo/record_explainer.py

Produces a .webm walkthrough plus assent-how-it-works.pdf. Set ASSENT_CHROME to use a
specific Chromium binary; ASSENT_OUT to change the output directory.
"""

import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROME = os.environ.get("ASSENT_CHROME")  # None => Playwright's bundled Chromium
REPO = Path(__file__).resolve().parent.parent
SC = Path(os.environ.get("ASSENT_OUT", REPO / "demo" / "out"))
SOURCE = REPO / "docs" / "how-it-works.html"
W, H = 1180, 820

CAPTION = """
(() => {
  const boot = () => {
    if (document.getElementById('__cap')) return;
    const c = document.createElement('div');
    c.id='__cap';
    c.style.cssText=`position:fixed;z-index:2147483647;left:50%;bottom:30px;
      transform:translateX(-50%) translateY(14px);opacity:0;
      background:rgba(14,16,24,.95);color:#fff;
      font:600 17px/1.5 ui-sans-serif,system-ui,sans-serif;
      padding:14px 26px;border-radius:12px;max-width:78vw;text-align:center;
      box-shadow:0 12px 44px rgba(0,0,0,.45);pointer-events:none;
      transition:opacity .35s ease, transform .35s ease;`;
    document.body.appendChild(c);
    window.__say = t => {
      const e=document.getElementById('__cap');
      if(!t){e.style.opacity='0';e.style.transform='translateX(-50%) translateY(14px)';return;}
      e.textContent=t;e.style.opacity='1';e.style.transform='translateX(-50%) translateY(0)';
    };
  };
  if (document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot);
  else boot();
})();
"""


def say(page, t, hold=3.4):
    page.evaluate("t => window.__say && window.__say(t)", t)
    time.sleep(hold)


def clear(page, hold=0.45):
    page.evaluate("() => window.__say && window.__say('')")
    time.sleep(hold)


def to(page, sel, offset=-90, settle=1.5):
    page.evaluate(
        """([s,o]) => { const el=document.querySelector(s);
             const y=el.getBoundingClientRect().top+window.scrollY+o;
             window.scrollTo({top:y,behavior:'smooth'}); }""",
        [sel, offset],
    )
    time.sleep(settle)


def creep(page, px=280, steps=14, per=0.05):
    for _ in range(steps):
        page.mouse.wheel(0, px / steps)
        time.sleep(per)


def main():
    SC.mkdir(parents=True, exist_ok=True)
    out = SC / "video_explainer"
    out.mkdir(exist_ok=True)

    # The page is a fragment (title + style + body); wrap it for standalone rendering.
    standalone = SC / "how-it-works.full.html"
    standalone.write_text(
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        + SOURCE.read_text(),
        encoding="utf-8",
    )
    page_url = standalone.as_uri()

    with sync_playwright() as p:
        launch = {"args": ["--force-color-profile=srgb"]}
        if CHROME:
            launch["executable_path"] = CHROME
        b = p.chromium.launch(**launch)
        ctx = b.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=str(out),
            record_video_size={"width": W, "height": H},
            color_scheme="light",
        )
        page = ctx.new_page()
        page.add_init_script(CAPTION)
        page.goto(page_url)
        page.wait_for_timeout(900)

        say(page, "How Assent actually works — the machinery under the product.", 3.6)
        clear(page)

        to(page, "#job")
        say(page, "It answers one question: is this action safe to run alone — and if not, who says yes?", 4.2)
        clear(page)
        creep(page, 320)
        say(page, "Three possible answers. Every path lands on one of them.", 3.4)
        clear(page)
        creep(page, 300)
        say(page, "Crucially, it scores risk-to-ACT, not how scary the threat is.", 3.8)
        clear(page)

        to(page, "#invariant")
        say(page, "One rule decides what's allowed to be AI at all.", 3.2)
        clear(page)
        creep(page, 300)
        say(page, "Measured facts can earn autonomy. Anything the model says can only pull toward a human.", 4.6)
        clear(page)
        creep(page, 260)
        say(page, "So confidence never authorizes anything — the break from '99% sure, go ahead.'", 4.4)
        clear(page)

        to(page, "#pipeline", -70)
        say(page, "The full pipeline, from detection to action.", 3.0)
        clear(page)
        creep(page, 240)
        say(page, "Only two stages are AI. Neither can widen what the gate permits.", 4.0)
        clear(page)
        say(page, "The dashed red paths are the fail-safes — each one ends at a human, never a guess.", 4.4)
        clear(page)

        to(page, "#envelope")
        say(page, "Risk is measured on four axes. Three are facts; one is an opinion.", 4.0)
        clear(page)
        creep(page, 330)
        say(page, "Reversibility is fixed per action type — it can't be argued down in the moment.", 4.2)
        clear(page)

        to(page, "#gate")
        say(page, "Auto-execution is a checklist, not a score. Every item must pass.", 4.0)
        clear(page)
        creep(page, 340)
        say(page, "These are the shipped thresholds — the autonomy dial each customer earns.", 4.0)
        clear(page)
        creep(page, 330)
        say(page, "Note where the AI-influenced steps sit: only as ways OUT of auto-execution.", 4.4)
        clear(page)

        to(page, "#ownership")
        say(page, "Approvals are useless if they reach the wrong person. So ownership is scored too.", 4.4)
        clear(page)
        creep(page, 320)
        say(page, "Ownership is derived from what a company already has — not a database they must fill in.", 4.6)
        clear(page)
        creep(page, 340)
        say(page, "Beliefs decay. A year-old claim drops below the routing floor and stops being trusted.", 4.6)
        clear(page)
        creep(page, 330)
        say(page, "Independent sources agreeing compound. One cloud tag isn't enough to route production.", 4.6)
        clear(page)
        creep(page, 300)
        say(page, "And every human approval teaches the graph — it learns from normal use.", 4.2)
        clear(page)

        to(page, "#audit")
        say(page, "A second agent scores it independently — and never sees the first one's answer.", 4.6)
        clear(page)
        creep(page, 340)
        say(page, "It starts at 1.0 and multiplies down for each risk factor it measures itself.", 4.2)
        clear(page)
        creep(page, 320)
        say(page, "Two ways it forces a human: it dissents, or the two simply disagree too much.", 4.4)
        clear(page)
        creep(page, 300)
        say(page, "Here's the real one: the agent was 91% sure. The auditor landed at 17.6%.", 4.6)
        clear(page)
        creep(page, 200)
        say(page, "Two independent reasons to stop — and it stopped.", 3.6)
        clear(page)

        to(page, "#missing")
        say(page, "The behavior that matters most: what happens when it doesn't know something.", 4.4)
        clear(page)
        creep(page, 330)
        say(page, "Missing data always degrades to 'ask a human' — never to 'guess and act.'", 4.4)
        clear(page)

        to(page, "#worked")
        say(page, "Five real detections, end to end. Every number here comes from the running system.", 4.6)
        clear(page)
        creep(page, 340)
        say(page, "Two ran themselves. Two escalated. One had no playbook, so it made no move at all.", 4.6)
        clear(page)
        creep(page, 340)
        say(page, "This one knew a plausible owner — and still refused to trust it.", 4.2)
        clear(page)

        to(page, "#ledger")
        say(page, "Every step is hash-chained, so the record can't be quietly edited afterward.", 4.4)
        clear(page)
        creep(page, 300)
        say(page, "That's the answer to 'who allowed this' — provable, not asserted.", 4.2)
        clear(page)

        to(page, "#scope")
        say(page, "And an honest map of what's real versus still a placeholder.", 4.0)
        clear(page)
        creep(page, 330)
        say(page, "The safety rails were built first — so a model dropped in inherits every constraint.", 4.8)
        clear(page)
        creep(page, 260)
        say(page, "The engineering is done. The open question is commercial.", 4.0)
        clear(page)
        time.sleep(1.2)

        path = page.video.path()
        ctx.close()

        # --- PDF export (fresh context, no captions, light theme) ---
        ctx2 = b.new_context(color_scheme="light")
        pg2 = ctx2.new_page()
        pg2.goto(page_url)
        pg2.wait_for_timeout(800)
        pg2.emulate_media(media="print")
        pg2.pdf(
            path=str(SC / "assent-how-it-works.pdf"),
            format="A4",
            print_background=True,
            margin={"top": "14mm", "bottom": "16mm", "left": "13mm", "right": "13mm"},
            display_header_footer=True,
            header_template="<div></div>",
            footer_template=(
                '<div style="width:100%;font-size:8px;color:#8a92a3;'
                'font-family:system-ui,sans-serif;padding:0 13mm;display:flex;'
                'justify-content:space-between"><span>Assent — How Assent decides</span>'
                '<span class="pageNumber"></span></div>'
            ),
        )
        ctx2.close()
        b.close()
        print("video:", path)


if __name__ == "__main__":
    main()
