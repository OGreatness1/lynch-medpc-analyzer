"""Visual layer for the Streamlit app: one designed theme, CSS and a few HTML blocks.

Everything here is presentation only - no analysis code depends on it.

ONE theme ("midnight lab"), defined twice in lock-step: Streamlit's colours in
.streamlit/config.toml and the PALETTE below. The first visual refresh guessed
light vs dark from st.context.theme; on Streamlit Cloud that guess disagreed
with what Streamlit actually drew (dark widgets under light styling), and
Streamlit exposes no theme CSS variables to detect it reliably. So the theme
is fixed and the viewer theme switcher is hidden (client.toolbarMode).

Motion is CSS-only (no JavaScript), on pseudo-elements of the app's outer
containers plus inline SVG, animating only transform / opacity /
stroke-dashoffset. It never intercepts clicks and is switched off entirely
when the viewer's system asks for reduced motion.

  * .stApp::before                    slow-drifting colour glow
  * .stApp::after                     faint dot grid, like graph paper
  * stAppViewContainer::before/after  two parallax layers of floating particles
  * hero                              a cumulative record that draws itself:
                                      response steps, pen resets at the top,
                                      infusion pips, an event raster below
"""
from __future__ import annotations

import random
from datetime import datetime
from typing import Iterable, Tuple

import streamlit as st

# Keep in step with [theme] in .streamlit/config.toml.
PALETTE = {
    "bg": "#090D18",
    "glow1": "rgba(91, 124, 255, .30)", "glow2": "rgba(163, 116, 255, .22)",
    "glow3": "rgba(46, 230, 197, .14)", "grid": "rgba(148, 163, 214, .085)",
    "particle": "rgba(160, 185, 255, .60)", "particle2": "rgba(196, 170, 255, .42)",
    "card": "rgba(17, 24, 42, .66)", "card-hover": "rgba(22, 31, 54, .80)",
    "border": "rgba(120, 140, 200, .16)", "border-hi": "rgba(120, 150, 255, .38)",
    "shadow": "rgba(0, 0, 0, .55)", "text": "#E7EBF4", "soft": "#93A0BC",
    "faint": "rgba(147, 160, 188, .35)",
    "a1": "#6D8CFF", "a2": "#A374FF", "a3": "#2EE6C5",
}

FONTS = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700"
         "&family=Space+Grotesk:wght@500;600;700&display=swap")


def _particles(n: int, size: int, seed: int, var: str) -> str:
    """Box-shadow list of n dots over two stacked viewports, so a
    translateY(-100vh) loop is seamless."""
    rng = random.Random(seed)
    dots = []
    for _ in range(n):
        x, y = rng.uniform(0, 100), rng.uniform(0, 100)
        blur = rng.choice((0, 1, 2))
        for dy in (0, 100):
            dots.append(f"{x:.2f}vw {y + dy:.2f}vh {blur}px {size // 2}px var({var})")
    return ", ".join(dots)


def inject_global_style() -> None:
    """The whole app's CSS. Call once per run, near the top."""
    root = "".join(f"--ui-{k}: {v};" for k, v in PALETTE.items())
    near = _particles(34, 2, seed=7, var="--ui-particle")
    far = _particles(20, 3, seed=11, var="--ui-particle2")

    st.markdown(f"""<style>
@import url('{FONTS}');
:root {{ {root} }}

/* ── Background motion ───────────────────────────────────────────────── */
.stApp {{ background: radial-gradient(120% 80% at 50% -10%, #111A33 0%, var(--ui-bg) 55%) fixed; }}
.stApp::before {{
  content: ""; position: fixed; inset: -25%; z-index: 0; pointer-events: none;
  background:
    radial-gradient(36% 30% at 16% 20%, var(--ui-glow1), transparent 70%),
    radial-gradient(32% 28% at 84% 16%, var(--ui-glow2), transparent 70%),
    radial-gradient(40% 36% at 62% 88%, var(--ui-glow3), transparent 72%);
  animation: ui-aurora 46s ease-in-out infinite alternate; will-change: transform;
}}
.stApp::after {{
  content: ""; position: fixed; inset: -40px; z-index: 0; pointer-events: none;
  background-image: radial-gradient(circle, var(--ui-grid) 1px, transparent 1.4px);
  background-size: 30px 30px;
  -webkit-mask-image: radial-gradient(ellipse 85% 65% at 50% 0%, #000 10%, transparent 78%);
          mask-image: radial-gradient(ellipse 85% 65% at 50% 0%, #000 10%, transparent 78%);
  animation: ui-grid 80s linear infinite;
}}
[data-testid="stAppViewContainer"]::before,
[data-testid="stAppViewContainer"]::after {{
  content: ""; position: fixed; top: 0; left: 0; width: 1px; height: 1px;
  z-index: 0; pointer-events: none; border-radius: 50%; will-change: transform;
}}
[data-testid="stAppViewContainer"]::before {{ box-shadow: {near}; animation: ui-rise 150s linear infinite; opacity: .55; }}
[data-testid="stAppViewContainer"]::after  {{ box-shadow: {far};  animation: ui-rise 240s linear infinite; opacity: .35; }}
[data-testid="stMain"], [data-testid="stSidebar"] {{ position: relative; z-index: 2; }}
[data-testid="stHeader"] {{ background: transparent !important; }}

@keyframes ui-aurora {{
  0%   {{ transform: translate3d(-3%, -2%, 0) rotate(0deg)  scale(1);    }}
  50%  {{ transform: translate3d( 2%,  3%, 0) rotate(6deg)  scale(1.06); }}
  100% {{ transform: translate3d( 4%, -1%, 0) rotate(-4deg) scale(1.03); }}
}}
@keyframes ui-grid    {{ to {{ transform: translate3d(30px, 30px, 0); }} }}
@keyframes ui-rise    {{ to {{ transform: translate3d(0, -100vh, 0); }} }}
@keyframes ui-in      {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes ui-shimmer {{ to {{ background-position: 300% 50%; }} }}
@keyframes ui-flow    {{ to {{ stroke-dashoffset: -40; }} }}
@keyframes ui-pulse   {{ 0%, 100% {{ opacity: .35; }} 50% {{ opacity: 1; }} }}
@keyframes ui-float   {{ 0%, 100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-4px); }} }}
@keyframes ui-draw {{
  0%   {{ stroke-dashoffset: 1000; opacity: 0; }}
  3%   {{ opacity: 1; }}
  74%  {{ stroke-dashoffset: 0; opacity: 1; }}
  93%  {{ stroke-dashoffset: 0; opacity: 1; }}
  100% {{ stroke-dashoffset: 0; opacity: 0; }}
}}

/* ── Typography ──────────────────────────────────────────────────────── */
html, body, .stApp {{ font-family: 'Inter', 'Segoe UI', system-ui, sans-serif; }}
h1, h2, h3, h4, .ui-title, .ui-greet, .ui-step-title {{ font-family: 'Space Grotesk', 'Inter', sans-serif !important; }}
.block-container {{ padding-top: 2.6rem; padding-bottom: 3rem; }}

/* ── Sidebar ─────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, rgba(14, 20, 38, .92), rgba(9, 13, 24, .94)) !important;
  -webkit-backdrop-filter: blur(16px); backdrop-filter: blur(16px);
  border-right: 1px solid var(--ui-border);
}}
[data-testid="stSidebar"] > div:first-child {{ background: transparent !important; }}
[data-testid="stSidebar"] h3 {{
  font-size: .95rem !important; letter-spacing: .02em; display: flex; align-items: center; gap: .55rem;
}}
[data-testid="stSidebar"] h3::before {{
  content: ""; width: 4px; height: 1.05em; border-radius: 4px;
  background: linear-gradient(180deg, var(--ui-a1), var(--ui-a2));
}}
[data-testid="stFileUploaderDropzone"] {{
  background: rgba(17, 24, 42, .55) !important;
  border: 1px dashed rgba(109, 140, 255, .35) !important; border-radius: 12px !important;
  transition: border-color .25s ease, box-shadow .25s ease, background .25s ease;
}}
[data-testid="stFileUploaderDropzone"]:hover {{
  border-color: var(--ui-a1) !important; background: rgba(22, 31, 54, .7) !important;
  box-shadow: 0 0 0 4px rgba(109, 140, 255, .10);
}}

/* ── Glass surfaces ──────────────────────────────────────────────────── */
[data-testid="stMetric"], [data-testid="stForm"], .ui-glass,
[data-testid="stPlotlyChart"], [data-testid="stExpander"] details,
div[class*="st-key-glass"] {{
  background: var(--ui-card) !important;
  border: 1px solid var(--ui-border) !important;
  border-radius: 16px;
  -webkit-backdrop-filter: blur(14px); backdrop-filter: blur(14px);
  box-shadow: 0 18px 40px -26px var(--ui-shadow), inset 0 1px 0 rgba(255, 255, 255, .04);
}}
[data-testid="stExpander"] details {{ border-radius: 12px !important; }}
[data-testid="stExpander"] summary:hover {{ color: var(--ui-a1); }}
[data-testid="stMetric"] {{
  padding: .85rem 1.05rem; position: relative; overflow: hidden;
  transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease;
  animation: ui-in .55s cubic-bezier(.2, .7, .2, 1) both;
}}
[data-testid="stMetric"]::before {{
  content: ""; position: absolute; inset: 0 0 auto 0; height: 2px;
  background: linear-gradient(90deg, var(--ui-a1), var(--ui-a2), var(--ui-a3)); opacity: .85;
}}
[data-testid="stMetric"]:hover {{
  transform: translateY(-2px); border-color: var(--ui-border-hi) !important;
  box-shadow: 0 22px 44px -24px var(--ui-shadow), 0 0 0 1px rgba(109, 140, 255, .08);
}}
[data-testid="stColumn"]:nth-child(2) [data-testid="stMetric"] {{ animation-delay: .05s; }}
[data-testid="stColumn"]:nth-child(3) [data-testid="stMetric"] {{ animation-delay: .10s; }}
[data-testid="stColumn"]:nth-child(4) [data-testid="stMetric"] {{ animation-delay: .15s; }}
[data-testid="stColumn"]:nth-child(5) [data-testid="stMetric"] {{ animation-delay: .20s; }}
[data-testid="stMetricLabel"] p {{ font-size: .78rem; letter-spacing: .04em; text-transform: uppercase; color: var(--ui-soft); }}
[data-testid="stMetricValue"] {{ font-family: 'Space Grotesk', 'Inter', sans-serif; font-size: 1.75rem; font-weight: 650; }}
/* No padding: Plotly sizes itself to the element's full width. Its own
   paper / plot backgrounds are cleared so the glass shows through. */
[data-testid="stPlotlyChart"] {{ padding: 0; overflow: hidden; animation: ui-in .6s ease both; }}
[data-testid="stPlotlyChart"] .main-svg {{ background: transparent !important; }}
[data-testid="stPlotlyChart"] .bg {{ fill: transparent !important; }}
[data-testid="stForm"] {{ padding: 1.5rem 1.5rem .7rem; animation: ui-in .6s ease both; }}
div[class*="st-key-glass"] {{ padding: 1.15rem 1.25rem; animation: ui-in .6s ease both; }}

/* ── Buttons, pills, segments ────────────────────────────────────────── */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {{
  background: linear-gradient(135deg, var(--ui-a1), var(--ui-a2)) !important;
  border: 0 !important; color: #fff !important; font-weight: 600;
  box-shadow: 0 10px 26px -12px var(--ui-a1);
  position: relative; overflow: hidden;
  transition: transform .2s ease, box-shadow .2s ease, filter .2s ease;
}}
[data-testid="stBaseButton-primary"]::after, [data-testid="stBaseButton-primaryFormSubmit"]::after {{
  content: ""; position: absolute; top: 0; left: -60%; width: 40%; height: 100%;
  background: linear-gradient(100deg, transparent, rgba(255, 255, 255, .32), transparent);
  transform: skewX(-20deg); transition: left .65s ease;
}}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {{
  transform: translateY(-1px); filter: brightness(1.07); box-shadow: 0 14px 30px -12px var(--ui-a2);
}}
[data-testid="stBaseButton-primary"]:hover::after,
[data-testid="stBaseButton-primaryFormSubmit"]:hover::after {{ left: 120%; }}
[data-testid="stBaseButton-primary"]:disabled {{
  background: rgba(109, 140, 255, .12) !important; color: var(--ui-soft) !important;
  box-shadow: none; filter: none; border: 1px solid var(--ui-border) !important;
}}
[data-testid="stBaseButton-segmented_controlActive"], [data-testid="stBaseButton-pillsActive"] {{
  background: linear-gradient(135deg, rgba(109, 140, 255, .22), rgba(163, 116, 255, .20)) !important;
  border-color: rgba(109, 140, 255, .60) !important; color: #fff !important;
  box-shadow: 0 0 0 3px rgba(109, 140, 255, .12), 0 8px 20px -12px var(--ui-a1);
}}
[data-testid="stBaseButton-segmented_control"], [data-testid="stBaseButton-pills"] {{
  transition: transform .15s ease, background .2s ease, border-color .2s ease;
}}
[data-testid="stBaseButton-pills"]:hover, [data-testid="stBaseButton-segmented_control"]:hover {{
  border-color: var(--ui-border-hi) !important;
}}
[data-testid="stBaseButton-pills"]:hover {{ transform: translateY(-1px); }}

/* ── Hero ────────────────────────────────────────────────────────────── */
.ui-hero {{ display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
           gap: 1.6rem; align-items: center; margin: .1rem 0 1.4rem;
           animation: ui-in .7s cubic-bezier(.2, .7, .2, 1) both; }}
.ui-hero.compact, .ui-hero.stack {{ grid-template-columns: minmax(0, 1fr); gap: 1rem; }}
.ui-hero.compact .ui-viz {{ display: none; }}
.ui-brand {{ display: flex; align-items: center; gap: 1.05rem; }}
.ui-logo {{ width: 50px; height: 72px; flex: none; animation: ui-float 6s ease-in-out infinite;
           filter: drop-shadow(0 0 10px rgba(109, 140, 255, .35)); }}
.ui-hero.compact .ui-logo {{ width: 38px; height: 54px; }}
.ui-logo .strand {{ fill: none; stroke-width: 3.2; stroke-linecap: round;
                   stroke-dasharray: 30 10; animation: ui-flow 2.8s linear infinite; }}
.ui-logo .strand.a {{ stroke: var(--ui-a1); }}
.ui-logo .strand.b {{ stroke: var(--ui-a2); animation-direction: reverse; }}
.ui-logo .rung {{ stroke: var(--ui-a3); stroke-width: 2.2; stroke-linecap: round;
                 animation: ui-pulse 2.4s ease-in-out infinite; }}
.ui-logo .rung:nth-of-type(2) {{ animation-delay: .4s; }}
.ui-logo .rung:nth-of-type(3) {{ animation-delay: .8s; }}
.ui-logo .rung:nth-of-type(4) {{ animation-delay: 1.2s; }}
.ui-logo .rung:nth-of-type(5) {{ animation-delay: 1.6s; }}
.ui-logo .rung:nth-of-type(6) {{ animation-delay: 2.0s; }}
.ui-badge {{ display: inline-flex; align-items: center; gap: .45rem; font-size: .7rem; font-weight: 600;
            letter-spacing: .14em; text-transform: uppercase; padding: .28rem .7rem; border-radius: 999px;
            color: #C9D4FF; border: 1px solid rgba(109, 140, 255, .35); background: rgba(109, 140, 255, .10); }}
.ui-badge::before {{ content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--ui-a3);
                    box-shadow: 0 0 8px var(--ui-a3); animation: ui-pulse 2.4s ease-in-out infinite; }}
.ui-title {{ font-size: clamp(2rem, 1.2rem + 2.8vw, 3.3rem); font-weight: 700; color: #F4F6FC;
            line-height: 1.02; letter-spacing: -.03em; margin: .55rem 0 .45rem; }}
.ui-hero.compact .ui-title {{ font-size: clamp(1.5rem, 1rem + 1.6vw, 2.1rem); margin: .4rem 0 .3rem; }}
.ui-grad {{ background: linear-gradient(90deg, var(--ui-a1), var(--ui-a3), var(--ui-a2), var(--ui-a1));
           background-size: 300% 100%; -webkit-background-clip: text; background-clip: text;
           color: transparent; animation: ui-shimmer 16s linear infinite; }}
.ui-sub {{ color: var(--ui-soft); font-size: .98rem; line-height: 1.55; margin: 0; max-width: 40rem; }}

/* Cumulative-record motion graphic */
.ui-viz {{ padding: .85rem 1rem .55rem; border-radius: 18px; background: var(--ui-card);
          border: 1px solid var(--ui-border); -webkit-backdrop-filter: blur(14px); backdrop-filter: blur(14px);
          box-shadow: 0 24px 50px -30px var(--ui-shadow), inset 0 1px 0 rgba(255, 255, 255, .05); }}
.ui-viz-cap {{ display: flex; justify-content: space-between; align-items: center;
              font-size: .64rem; font-weight: 600; letter-spacing: .16em; text-transform: uppercase;
              color: var(--ui-soft); margin-bottom: .35rem; }}
.ui-viz-cap .live {{ display: inline-flex; align-items: center; gap: .4rem; color: var(--ui-a3); }}
.ui-viz-cap .live::before {{ content: ""; width: 6px; height: 6px; border-radius: 50%;
                            background: var(--ui-a3); box-shadow: 0 0 8px var(--ui-a3);
                            animation: ui-pulse 1.6s ease-in-out infinite; }}
.ui-cumrec {{ width: 100%; height: auto; display: block; }}
.ui-cumrec .gl {{ stroke: rgba(147, 160, 188, .12); stroke-width: 1; }}
.ui-cumrec .ev {{ stroke: var(--ui-a2); stroke-width: 1.3; opacity: .55; }}
.ui-cumrec .trace {{ fill: none; stroke: var(--ui-a3); stroke-width: 1.9; stroke-linejoin: round;
                    stroke-dasharray: 1000; stroke-dashoffset: 1000;
                    filter: drop-shadow(0 0 5px rgba(46, 230, 197, .55));
                    animation: ui-draw 13s linear infinite; }}
.ui-cumrec .lbl {{ fill: var(--ui-soft); font-size: 9px; letter-spacing: .12em; font-family: 'Inter', sans-serif; }}

/* ── Welcome card ────────────────────────────────────────────────────── */
.ui-greet {{ font-size: 1.15rem; font-weight: 600; margin: 0 0 1rem; color: #F4F6FC; }}
.ui-greet span {{ color: var(--ui-soft); font-weight: 500; font-family: 'Inter', sans-serif; font-size: .98rem; }}
.ui-steps {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: .9rem; }}
.ui-step {{ position: relative; padding: 1.05rem 1.1rem 1.1rem; border-radius: 14px;
           border: 1px solid var(--ui-border); background: rgba(12, 18, 34, .55);
           transition: transform .25s ease, border-color .25s ease, background .25s ease;
           animation: ui-in .6s ease both; overflow: hidden; }}
.ui-step::after {{ content: ""; position: absolute; inset: auto -30% -60% auto; width: 140px; height: 140px;
                  border-radius: 50%; background: radial-gradient(circle, rgba(109, 140, 255, .16), transparent 70%);
                  transition: transform .4s ease; }}
.ui-step:nth-child(2) {{ animation-delay: .08s; }}
.ui-step:nth-child(3) {{ animation-delay: .16s; }}
.ui-step:hover {{ transform: translateY(-3px); border-color: var(--ui-border-hi); background: rgba(17, 25, 46, .7); }}
.ui-step:hover::after {{ transform: scale(1.25); }}
.ui-step .ui-num {{ display: inline-grid; place-items: center; width: 30px; height: 30px; border-radius: 9px;
                   font-weight: 700; font-size: .85rem; color: #fff; margin-bottom: .7rem;
                   background: linear-gradient(135deg, var(--ui-a1), var(--ui-a2));
                   box-shadow: 0 8px 18px -8px var(--ui-a2); }}
.ui-step .ui-step-title {{ display: block; font-size: 1.02rem; font-weight: 650; color: #F4F6FC; margin-bottom: .3rem; }}
.ui-step .ui-step-text {{ display: block; color: var(--ui-soft); font-size: .9rem; line-height: 1.5; }}
.ui-step .ui-step-text b {{ color: var(--ui-text); }}

.ui-foot {{ text-align: center; color: var(--ui-soft); font-size: .78rem; margin-top: 2.4rem; opacity: .85;
           letter-spacing: .02em; }}
.ui-foot .dot {{ display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin: 0 .55rem 1px;
                background: var(--ui-a3); box-shadow: 0 0 8px var(--ui-a3); animation: ui-pulse 2.6s ease-in-out infinite; }}

/* ── Small screens ───────────────────────────────────────────────────── */
@media (max-width: 900px) {{ .ui-hero {{ grid-template-columns: minmax(0, 1fr); }} }}
@media (max-width: 640px) {{
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"]) {{
    flex-wrap: wrap !important; gap: .5rem !important; }}
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"]) > [data-testid="stColumn"] {{
    flex: 1 1 30% !important; min-width: 7.5rem !important; }}
  .ui-logo {{ width: 38px; height: 54px; }}
}}

/* Respect the viewer's reduced-motion setting: no animation at all, and the
   cumulative record is shown fully drawn instead of hidden. */
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ animation: none !important; transition: none !important; }}
  .ui-cumrec .trace {{ stroke-dashoffset: 0 !important; }}
}}
</style>""", unsafe_allow_html=True)


LOGO_SVG = """<svg class="ui-logo" viewBox="0 0 40 64" aria-hidden="true">
<line class="rung" x1="12" y1="6"  x2="28" y2="6"/>
<line class="rung" x1="10" y1="18" x2="30" y2="18"/>
<line class="rung" x1="12" y1="26" x2="28" y2="26"/>
<line class="rung" x1="12" y1="38" x2="28" y2="38"/>
<line class="rung" x1="10" y1="46" x2="30" y2="46"/>
<line class="rung" x1="12" y1="58" x2="28" y2="58"/>
<path class="strand a" d="M8 2 C8 12 32 12 32 22 S8 32 8 42 S32 52 32 62"/>
<path class="strand b" d="M32 2 C32 12 8 12 8 22 S32 32 32 42 S8 52 8 62"/>
</svg>"""


def _cumulative_record_svg(seed: int = 3) -> str:
    """A cumulative record, as a MedPC cumulative recorder would draw it.

    Bursts of responding step the pen up, the pen resets to the baseline when
    it reaches the top, and every 7th response gets an infusion pip. An event
    raster of the same responses runs underneath. Illustrative only - it is a
    fixed, seeded pattern, not anyone's data.
    """
    rng = random.Random(seed)
    W, x0, x1, base, top = 560, 16, 544, 132, 18
    times, t = [], 0.02
    while t < 0.97:
        if rng.random() < 0.6:
            for _ in range(rng.randint(9, 24)):
                t += rng.uniform(0.0016, 0.0055)
                times.append(t)
        t += rng.uniform(0.025, 0.07)
    times = [x for x in times if x < 0.97]

    step, y = 3.4, base
    d = [f"M{x0} {base}"]
    for i, tt in enumerate(times):
        x = x0 + tt * (x1 - x0)
        d.append(f"H{x:.1f}")
        if y - step < top:              # pen reset, as on a real recorder
            d.append(f"V{base}")
            y = base
        y -= step
        d.append(f"V{y:.1f}")
        if i % 7 == 6:                  # infusion pip
            d.append("l4 5 l-4 -5")
    d.append(f"H{x1}")

    grid = "".join(f'<line class="gl" x1="{x0}" y1="{gy}" x2="{x1}" y2="{gy}"/>'
                   for gy in (top, (top + base) // 2, base))
    raster = "".join(f'<line class="ev" x1="{x0 + tt * (x1 - x0):.1f}" y1="146" x2="{x0 + tt * (x1 - x0):.1f}" y2="154"/>'
                     for tt in times)
    return (f'<svg class="ui-cumrec" viewBox="0 0 {W} 164" preserveAspectRatio="none" aria-hidden="true">'
            f'{grid}<path class="trace" pathLength="1000" d="{" ".join(d)}"/>{raster}'
            f'<text class="lbl" x="{x0}" y="163">RESPONSES</text></svg>')


CUMREC_SVG = _cumulative_record_svg()


def hero(badge: str, title: str, accent: str, subtitle: str = "",
         compact: bool = False, stack: bool = False, viz: bool = True) -> None:
    """Brand header. `viz` adds the cumulative-record panel (hidden when compact)."""
    cls = "ui-hero" + (" compact" if compact else "") + (" stack" if stack else "")
    sub = f'<p class="ui-sub">{subtitle}</p>' if subtitle else ""
    panel = (f'<div class="ui-viz"><div class="ui-viz-cap"><span>Cumulative record</span>'
             f'<span class="live">recording</span></div>{CUMREC_SVG}</div>') if viz and not compact else ""
    st.markdown(
        f'<div class="{cls}"><div class="ui-brand">{LOGO_SVG}<div>'
        f'<span class="ui-badge">{badge}</span>'
        f'<div class="ui-title" role="heading" aria-level="1">{title} <span class="ui-grad">{accent}</span></div>'
        f"{sub}</div></div>{panel}</div>",
        unsafe_allow_html=True)


def greeting() -> str:
    """'Good morning' etc. in the VIEWER's time zone (the server runs UTC)."""
    hour = None
    try:
        from zoneinfo import ZoneInfo
        tz = st.context.timezone
        if tz:
            hour = datetime.now(ZoneInfo(tz)).hour
    except Exception:
        hour = None
    if hour is None:
        return "Welcome"
    return "Good morning" if 5 <= hour < 12 else "Good afternoon" if 12 <= hour < 18 else "Good evening"


def steps(items: Iterable[Tuple[str, str]], intro: str = "", aside: str = "") -> None:
    cards = "".join(
        f'<div class="ui-step"><span class="ui-num">{i:02d}</span>'
        f'<span class="ui-step-title">{t}</span><span class="ui-step-text">{d}</span></div>'
        for i, (t, d) in enumerate(items, 1))
    head = f'<p class="ui-greet">{intro} <span>{aside}</span></p>' if intro else ""
    st.markdown(f'<div class="ui-glass" style="padding:1.35rem 1.4rem 1.4rem">{head}'
                f'<div class="ui-steps">{cards}</div></div>', unsafe_allow_html=True)


def footer(version: str) -> None:
    st.markdown(f'<div class="ui-foot">Lynch Lab · University of Virginia<span class="dot"></span>'
                f'MedPC Analyzer v{version}</div>', unsafe_allow_html=True)
