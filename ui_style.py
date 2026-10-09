"""Visual layer for the Streamlit app: theme-aware CSS and a few HTML blocks.

Everything here is presentation only - no analysis code depends on it.

Motion is CSS-only (no JavaScript) and lives on pseudo-elements of the app's
outer containers, so it never intercepts clicks, survives Streamlit's HTML
sanitiser, and only animates `transform` / `opacity` (GPU-cheap):

  * .stApp::before                 slow-drifting colour glow ("aurora")
  * .stApp::after                  faint dot grid, like lab graph paper
  * stAppViewContainer::before/after  two parallax layers of floating
                                    particles, drawn as box-shadows of one dot

All of it is switched off for viewers whose system asks for reduced motion.
"""
from __future__ import annotations

import random
from datetime import datetime
from typing import Iterable, Optional, Tuple

import streamlit as st

# Light / dark palettes. Accents follow .streamlit/config.toml's primaryColor.
PALETTES = {
    "light": {
        "glow1": "rgba(37, 99, 235, .18)",   "glow2": "rgba(124, 58, 237, .13)",
        "glow3": "rgba(13, 148, 136, .14)",  "grid": "rgba(15, 23, 42, .09)",
        "particle": "rgba(37, 99, 235, .38)", "particle2": "rgba(124, 58, 237, .28)",
        "card": "rgba(255, 255, 255, .70)",  "card_hover": "rgba(255, 255, 255, .86)",
        "border": "rgba(15, 23, 42, .09)",   "shadow": "rgba(15, 23, 42, .10)",
        "sidebar": "rgba(247, 249, 252, .78)", "header": "rgba(255, 255, 255, .55)",
        "soft": "#475569", "a1": "#2563EB", "a2": "#7C3AED", "a3": "#0D9488",
    },
    "dark": {
        "glow1": "rgba(59, 130, 246, .26)",  "glow2": "rgba(168, 85, 247, .20)",
        "glow3": "rgba(45, 212, 191, .16)",  "grid": "rgba(148, 163, 184, .10)",
        "particle": "rgba(147, 197, 253, .55)", "particle2": "rgba(196, 181, 253, .40)",
        "card": "rgba(22, 28, 40, .62)",     "card_hover": "rgba(28, 35, 50, .78)",
        "border": "rgba(148, 163, 184, .16)", "shadow": "rgba(0, 0, 0, .45)",
        "sidebar": "rgba(15, 20, 30, .72)",  "header": "rgba(14, 17, 23, .45)",
        "soft": "#94A3B8", "a1": "#60A5FA", "a2": "#A78BFA", "a3": "#2DD4BF",
    },
}


def theme_type() -> Optional[str]:
    """'light' / 'dark' from the viewer's active Streamlit theme, else None."""
    try:
        t = st.context.theme.type
    except Exception:
        t = None
    return t if t in PALETTES else None


def _vars(p: dict) -> str:
    return "".join(f"--ui-{k.replace('_', '-')}: {v};" for k, v in p.items())


def _particles(n: int, size: int, seed: int, var: str) -> str:
    """Box-shadow list of n dots spread over two stacked viewports, so a
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
    """Theme-aware CSS for the whole app. Call once per run, near the top."""
    t = theme_type()
    if t:
        root = f":root {{{_vars(PALETTES[t])}}}"
    else:
        # Theme not reported yet (first paint): follow the system setting.
        root = (f":root {{{_vars(PALETTES['light'])}}}"
                f"@media (prefers-color-scheme: dark) {{:root {{{_vars(PALETTES['dark'])}}}}}")

    near = _particles(34, 2, seed=7, var="--ui-particle")
    far = _particles(20, 3, seed=11, var="--ui-particle2")

    st.markdown(f"""<style>
{root}

/* ── Background motion ───────────────────────────────────────────────── */
.stApp::before {{
  content: ""; position: fixed; inset: -25%; z-index: 0; pointer-events: none;
  background:
    radial-gradient(38% 32% at 18% 22%, var(--ui-glow1), transparent 70%),
    radial-gradient(34% 30% at 82% 18%, var(--ui-glow2), transparent 70%),
    radial-gradient(42% 38% at 62% 86%, var(--ui-glow3), transparent 72%);
  animation: ui-aurora 42s ease-in-out infinite alternate;
  will-change: transform;
}}
.stApp::after {{
  content: ""; position: fixed; inset: -40px; z-index: 0; pointer-events: none;
  background-image: radial-gradient(circle, var(--ui-grid) 1px, transparent 1.4px);
  background-size: 30px 30px;
  -webkit-mask-image: radial-gradient(ellipse 80% 60% at 50% 0%, #000 10%, transparent 75%);
          mask-image: radial-gradient(ellipse 80% 60% at 50% 0%, #000 10%, transparent 75%);
  animation: ui-grid 70s linear infinite;
}}
[data-testid="stAppViewContainer"]::before,
[data-testid="stAppViewContainer"]::after {{
  content: ""; position: fixed; top: 0; left: 0; width: 1px; height: 1px;
  z-index: 0; pointer-events: none; border-radius: 50%; will-change: transform;
}}
[data-testid="stAppViewContainer"]::before {{
  box-shadow: {near};
  animation: ui-rise 140s linear infinite; opacity: .55;
}}
[data-testid="stAppViewContainer"]::after {{
  box-shadow: {far};
  animation: ui-rise 220s linear infinite; opacity: .35;
}}
[data-testid="stMain"], [data-testid="stSidebar"] {{ position: relative; z-index: 2; }}
[data-testid="stHeader"] {{
  background: var(--ui-header) !important;
  -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px);
}}

@keyframes ui-aurora {{
  0%   {{ transform: translate3d(-3%, -2%, 0) rotate(0deg)  scale(1);    }}
  50%  {{ transform: translate3d( 2%,  3%, 0) rotate(6deg)  scale(1.06); }}
  100% {{ transform: translate3d( 4%, -1%, 0) rotate(-4deg) scale(1.03); }}
}}
@keyframes ui-grid {{ to {{ transform: translate3d(30px, 30px, 0); }} }}
@keyframes ui-rise {{ to {{ transform: translate3d(0, -100vh, 0); }} }}
@keyframes ui-in   {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes ui-shimmer {{ to {{ background-position: 300% 50%; }} }}
@keyframes ui-flow {{ to {{ stroke-dashoffset: -40; }} }}
@keyframes ui-pulse {{ 0%, 100% {{ opacity: .35; }} 50% {{ opacity: 1; }} }}
@keyframes ui-float {{ 0%, 100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-4px); }} }}

/* ── Layout ──────────────────────────────────────────────────────────── */
.block-container {{ padding-top: 2.4rem; padding-bottom: 3rem; }}
[data-testid="stSidebar"] {{
  background: var(--ui-sidebar) !important;
  -webkit-backdrop-filter: blur(16px); backdrop-filter: blur(16px);
  border-right: 1px solid var(--ui-border);
}}
[data-testid="stSidebar"] > div:first-child {{ background: transparent !important; }}

/* ── Glass surfaces ──────────────────────────────────────────────────── */
[data-testid="stMetric"], [data-testid="stForm"], .ui-glass,
[data-testid="stPlotlyChart"], [data-testid="stExpander"] details,
div[class*="st-key-glass"] {{
  background: var(--ui-card);
  border: 1px solid var(--ui-border) !important;
  border-radius: 14px;
  -webkit-backdrop-filter: blur(12px); backdrop-filter: blur(12px);
  box-shadow: 0 10px 30px -18px var(--ui-shadow);
}}
[data-testid="stMetric"] {{
  padding: .8rem 1rem;
  transition: transform .25s ease, box-shadow .25s ease, background .25s ease;
  animation: ui-in .55s cubic-bezier(.2, .7, .2, 1) both;
  position: relative; overflow: hidden;
}}
[data-testid="stMetric"]::before {{
  content: ""; position: absolute; inset: 0 0 auto 0; height: 3px;
  background: linear-gradient(90deg, var(--ui-a1), var(--ui-a2), var(--ui-a3));
  opacity: .75;
}}
[data-testid="stMetric"]:hover {{
  transform: translateY(-2px); background: var(--ui-card-hover);
  box-shadow: 0 16px 34px -18px var(--ui-shadow);
}}
[data-testid="stColumn"]:nth-child(2) [data-testid="stMetric"] {{ animation-delay: .05s; }}
[data-testid="stColumn"]:nth-child(3) [data-testid="stMetric"] {{ animation-delay: .10s; }}
[data-testid="stColumn"]:nth-child(4) [data-testid="stMetric"] {{ animation-delay: .15s; }}
[data-testid="stColumn"]:nth-child(5) [data-testid="stMetric"] {{ animation-delay: .20s; }}
[data-testid="stMetricLabel"] p {{ font-size: .8rem; letter-spacing: .02em; color: var(--ui-soft); }}
[data-testid="stMetricValue"] {{ font-size: 1.65rem; font-weight: 650; }}
/* No padding: Plotly sizes itself to the element's full width, so padding
   pushed the right edge (legend) past the card. Its own paper / plot
   backgrounds are cleared so the glass shows through. */
[data-testid="stPlotlyChart"] {{ padding: 0; overflow: hidden; animation: ui-in .6s ease both; }}
[data-testid="stPlotlyChart"] .main-svg {{ background: transparent !important; }}
[data-testid="stPlotlyChart"] .bg {{ fill: transparent !important; }}
[data-testid="stForm"] {{ padding: 1.4rem 1.4rem .6rem; animation: ui-in .6s ease both; }}
div[class*="st-key-glass"] {{ padding: 1.1rem 1.2rem; animation: ui-in .6s ease both; }}

/* ── Buttons ─────────────────────────────────────────────────────────── */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {{
  background: linear-gradient(135deg, var(--ui-a1), var(--ui-a2)) !important;
  border: 0 !important; color: #fff !important;
  box-shadow: 0 8px 22px -10px var(--ui-a1);
  position: relative; overflow: hidden;
  transition: transform .2s ease, box-shadow .2s ease, filter .2s ease;
}}
[data-testid="stBaseButton-primary"]::after, [data-testid="stBaseButton-primaryFormSubmit"]::after {{
  content: ""; position: absolute; top: 0; left: -60%; width: 40%; height: 100%;
  background: linear-gradient(100deg, transparent, rgba(255, 255, 255, .35), transparent);
  transform: skewX(-20deg); transition: left .6s ease;
}}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {{
  transform: translateY(-1px); filter: brightness(1.06);
  box-shadow: 0 12px 26px -10px var(--ui-a2);
}}
[data-testid="stBaseButton-primary"]:hover::after,
[data-testid="stBaseButton-primaryFormSubmit"]:hover::after {{ left: 120%; }}
[data-testid="stBaseButton-primary"]:disabled {{ filter: grayscale(.6) opacity(.55); box-shadow: none; }}

[data-testid="stBaseButton-segmented_controlActive"], [data-testid="stBaseButton-pillsActive"] {{
  background: linear-gradient(135deg, color-mix(in srgb, var(--ui-a1) 18%, transparent),
                                      color-mix(in srgb, var(--ui-a2) 18%, transparent)) !important;
  border-color: color-mix(in srgb, var(--ui-a1) 55%, transparent) !important;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--ui-a1) 12%, transparent);
}}
[data-testid="stBaseButton-segmented_control"], [data-testid="stBaseButton-pills"] {{
  transition: transform .15s ease, background .2s ease;
}}
[data-testid="stBaseButton-pills"]:hover {{ transform: translateY(-1px); }}

/* ── Hero, logo, steps ───────────────────────────────────────────────── */
.ui-hero {{ display: flex; align-items: center; gap: 1rem; margin: .2rem 0 1.1rem;
           animation: ui-in .7s cubic-bezier(.2, .7, .2, 1) both; }}
.ui-hero.center {{ justify-content: center; text-align: left; }}
.ui-logo {{ width: 46px; height: 64px; flex: none; animation: ui-float 6s ease-in-out infinite; }}
.ui-hero.compact .ui-logo {{ width: 36px; height: 50px; }}
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
.ui-badge {{ display: inline-block; font-size: .72rem; font-weight: 600; letter-spacing: .08em;
            text-transform: uppercase; padding: .22rem .6rem; border-radius: 999px;
            color: var(--ui-a1); border: 1px solid color-mix(in srgb, var(--ui-a1) 35%, transparent);
            background: color-mix(in srgb, var(--ui-a1) 9%, transparent); }}
.ui-title {{ font-size: clamp(1.7rem, 1.1rem + 2.4vw, 2.7rem); font-weight: 760;
            line-height: 1.08; letter-spacing: -.02em; margin: .35rem 0 .3rem; }}
.ui-hero.compact .ui-title {{ font-size: clamp(1.4rem, 1rem + 1.6vw, 2rem); }}
.ui-grad {{ background: linear-gradient(90deg, var(--ui-a1), var(--ui-a2), var(--ui-a3), var(--ui-a1));
           background-size: 300% 100%; -webkit-background-clip: text; background-clip: text;
           color: transparent; animation: ui-shimmer 14s linear infinite; }}
.ui-sub {{ color: var(--ui-soft); font-size: .95rem; margin: 0; }}
.ui-greet {{ font-size: 1.05rem; font-weight: 600; margin: 0 0 .9rem; }}
.ui-steps {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: .9rem; }}
.ui-step {{ padding: 1rem 1.05rem; border-radius: 14px; border: 1px solid var(--ui-border);
           background: color-mix(in srgb, var(--ui-card) 60%, transparent);
           transition: transform .25s ease, border-color .25s ease;
           animation: ui-in .6s ease both; }}
.ui-step:nth-child(2) {{ animation-delay: .08s; }}
.ui-step:nth-child(3) {{ animation-delay: .16s; }}
.ui-step:hover {{ transform: translateY(-3px);
                 border-color: color-mix(in srgb, var(--ui-a1) 45%, transparent); }}
.ui-step .ui-num {{ display: inline-grid; place-items: center; width: 30px; height: 30px; border-radius: 50%;
          font-weight: 700; font-size: .9rem; color: #fff; margin-bottom: .55rem;
          background: linear-gradient(135deg, var(--ui-a1), var(--ui-a2));
          box-shadow: 0 6px 16px -8px var(--ui-a2); }}
.ui-step .ui-step-title {{ display: block; font-weight: 700; margin-bottom: .2rem; }}
.ui-step .ui-step-text {{ display: block; color: var(--ui-soft); font-size: .9rem; line-height: 1.45; }}
.ui-foot {{ text-align: center; color: var(--ui-soft); font-size: .8rem; margin-top: 2.2rem; opacity: .85; }}
.ui-foot .dot {{ display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin: 0 .5rem 1px;
                background: var(--ui-a3); animation: ui-pulse 2.6s ease-in-out infinite; }}

/* Narrow windows: summary cards 2-3 per row instead of one each. */
@media (max-width: 640px) {{
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"]) {{
    flex-wrap: wrap !important; gap: .5rem !important; }}
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"]) > [data-testid="stColumn"] {{
    flex: 1 1 30% !important; min-width: 7.5rem !important; }}
  .ui-logo {{ width: 36px; height: 50px; }}
}}

/* Respect the viewer's reduced-motion setting: no animation at all. */
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ animation: none !important; transition: none !important; }}
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


def hero(badge: str, title: str, accent: str, subtitle: str = "",
         compact: bool = False, center: bool = False) -> None:
    cls = "ui-hero" + (" compact" if compact else "") + (" center" if center else "")
    sub = f'<p class="ui-sub">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<div class="{cls}">{LOGO_SVG}<div>'
        f'<span class="ui-badge">{badge}</span>'
        f'<div class="ui-title" role="heading" aria-level="1">{title} <span class="ui-grad">{accent}</span></div>'
        f"{sub}</div></div>",
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


def steps(items: Iterable[Tuple[str, str]], intro: str = "") -> None:
    cards = "".join(
        f'<div class="ui-step"><span class="ui-num">{i}</span>'
        f'<span class="ui-step-title">{t}</span><span class="ui-step-text">{d}</span></div>'
        for i, (t, d) in enumerate(items, 1))
    head = f'<p class="ui-greet">{intro}</p>' if intro else ""
    st.markdown(f'<div class="ui-glass" style="padding:1.2rem 1.3rem">{head}'
                f'<div class="ui-steps">{cards}</div></div>', unsafe_allow_html=True)


def footer(version: str) -> None:
    st.markdown(f'<div class="ui-foot">Lynch Lab · University of Virginia<span class="dot"></span>'
                f'MedPC Analyzer v{version}</div>', unsafe_allow_html=True)
