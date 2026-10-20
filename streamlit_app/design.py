"""Shared design system for the Streamlit app."""

from __future__ import annotations

from html import escape
from urllib.parse import quote

import streamlit as st


PALETTE = {
    "bg": "#09131A",
    "surface": "#0F1D27",
    "surface_alt": "#132632",
    "text": "#EAF2F6",
    "muted": "#9AB0BB",
    "border": "#213A49",
    "brand": "#2FA38A",
    "brand_dark": "#1C6E5D",
    "accent": "#D8A24A",
    "accent_soft": "#30261A",
    "info": "#4C98D3",
    "success": "#39B982",
    "warning": "#D9A441",
    "danger": "#D46A60",
}

TONE_MAP = {
    "brand": (PALETTE["brand"], PALETTE["brand_dark"]),
    "info": (PALETTE["info"], "#18354E"),
    "success": (PALETTE["success"], "#154C3A"),
    "warning": (PALETTE["warning"], "#5A4116"),
    "danger": (PALETTE["danger"], "#5A231F"),
}

ICON_PATHS = {
    "sun": "M12 4V2m0 20v-2m8-8h2m-20 0h2m14.95 2.05-1.41 1.41M6.46 17.54l-1.41 1.41m12.9-1.41 1.41 1.41M6.46 6.46 5.05 5.05m12.9 1.41 1.41-1.41M12 8a4 4 0 100 8 4 4 0 000-8z",
    "bolt": "M11 21h-1l1-7H7.5a1 1 0 01-.8-1.6l6-8A1 1 0 0114.5 5l-1 6H17a1 1 0 01.8 1.6l-6 8A1 1 0 0111 21z",
    "idea": "M9 21h6m-7-3h8m-7-3.5V13a5 5 0 116 0v1.5",
    "alert": "M12 9v4m0 4h.01M10.29 3.86l-7.5 13A1 1 0 003.65 18h16.7a1 1 0 00.86-1.5l-7.5-13a1 1 0 00-1.72 0z",
    "forecast": "M4 18h16M7 14l3-3 2 2 5-6",
    "money": "M4 7h16v10H4zM8 12h8M8 9h.01M16 15h.01",
    "battery": "M17 7V6a1 1 0 00-1-1H4a1 1 0 00-1 1v12a1 1 0 001 1h12a1 1 0 001-1v-1m1-8h1a1 1 0 011 1v4a1 1 0 01-1 1h-1M7 10v4m3-6v8m3-5v2",
    "factory": "M3 21h18M5 21V9l5 3V9l5 3V5h4v16",
    "chart": "M5 19V9m7 10V5m7 14v-7M3 21h18",
    "spark": "M12 3l1.9 4.8L19 10l-5.1 2.2L12 17l-1.9-4.8L5 10l5.1-2.2L12 3z",
    "upload": "M12 16V7m0 0l-3 3m3-3l3 3M5 19h14",
    "download": "M12 8v9m0 0l-3-3m3 3l3-3M5 19h14",
    "settings": "M12 8a4 4 0 100 8 4 4 0 000-8zm8 4l-2 .5a7.7 7.7 0 01-.6 1.4l1.2 1.7-1.4 1.4-1.7-1.2a7.7 7.7 0 01-1.4.6L12 20l-2.1-.6a7.7 7.7 0 01-1.4-.6l-1.7 1.2-1.4-1.4 1.2-1.7a7.7 7.7 0 01-.6-1.4L4 12l.6-2.1c.1-.5.3-1 .6-1.4L4 6.8l1.4-1.4 1.7 1.2c.4-.3.9-.5 1.4-.6L12 4l2.1.6c.5.1 1 .3 1.4.6l1.7-1.2L18.6 6l-1.2 1.7c.3.4.5.9.6 1.4L20 12z",
    "cloud": "M7 18a4 4 0 010-8 5.5 5.5 0 0110.7-1.6A4.5 4.5 0 1117.5 18H7z",
    "check": "M5 13l4 4L19 7",
    "calendar": "M7 3v3m10-3v3M4 8h16M5 5h14a1 1 0 011 1v13a1 1 0 01-1 1H5a1 1 0 01-1-1V6a1 1 0 011-1z",
    "mail": "M4 6h16v12H4zM4 7l8 6 8-6",
    "person": "M12 12a4 4 0 100-8 4 4 0 000 8zm-7 8a7 7 0 0114 0",
    "lock": "M7 11V8a5 5 0 0110 0v3m-9 0h8a1 1 0 011 1v7H7v-7a1 1 0 011-1z",
    "report": "M7 3h7l5 5v13H7zM14 3v5h5M10 13h4m-4 4h4M10 9h1",
}


def inject_style_block(css: str) -> None:
    """Inject a raw CSS block. Keep usage centralized in design helpers."""
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_html_block(html: str) -> None:
    """Render controlled HTML using the most reliable Streamlit primitive available."""
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


def inject_css() -> None:
    """Inject global design tokens and component styles."""
    inject_style_block(
        f"""
        :root {{
            --bg: {PALETTE["bg"]};
            --surface: {PALETTE["surface"]};
            --surface-alt: {PALETTE["surface_alt"]};
            --text: {PALETTE["text"]};
            --muted: {PALETTE["muted"]};
            --border: {PALETTE["border"]};
            --brand: {PALETTE["brand"]};
            --brand-dark: {PALETTE["brand_dark"]};
            --accent: {PALETTE["accent"]};
            --accent-soft: {PALETTE["accent_soft"]};
            --info: {PALETTE["info"]};
            --success: {PALETTE["success"]};
            --warning: {PALETTE["warning"]};
            --danger: {PALETTE["danger"]};
        }}
        .stApp {{
            background:
                radial-gradient(circle at top left, rgba(216, 162, 74, 0.16), transparent 30%),
                radial-gradient(circle at top right, rgba(47, 163, 138, 0.14), transparent 26%),
                linear-gradient(180deg, #071118 0%, var(--bg) 36%, #07161F 100%);
            color: var(--text);
        }}
        [data-testid="stSidebar"] {{
            background: rgba(9, 19, 26, 0.96);
            border-right: 1px solid var(--border);
        }}
        .block-container {{
            padding-top: 3rem;
            padding-bottom: 2rem;
        }}
        h1, h2, h3, h4, p, label, div, span {{
            color: inherit;
        }}
        h1, h2, h3, h4 {{
            letter-spacing: -0.02em;
        }}
        [data-testid="stMetricValue"] {{
            font-size: 1.45rem;
            color: var(--text);
        }}
        [data-testid="stMetricLabel"] {{
            font-size: 0.92rem;
            color: var(--muted);
        }}
        [data-testid="stAlert"] {{
            border-radius: 16px;
            border: 1px solid var(--border);
        }}
        [data-baseweb="select"] > div,
        [data-baseweb="input"] > div,
        textarea,
        input {{
            background: rgba(15, 29, 39, 0.92) !important;
            color: var(--text) !important;
        }}
        .ag-card {{
            background: linear-gradient(180deg, rgba(16, 31, 41, 0.98), rgba(12, 24, 33, 0.98));
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 1rem 1.1rem;
            box-shadow: 0 18px 40px rgba(0, 0, 0, 0.22);
            color: var(--text);
            height: 100%;
        }}
        .ag-card__top {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.8rem;
            margin-bottom: 0.7rem;
        }}
        .ag-card__title {{
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text);
        }}
        .ag-card__badge {{
            display: inline-flex;
            margin-bottom: 0.55rem;
            font-size: 0.74rem;
            color: var(--muted);
            background: rgba(76, 152, 211, 0.12);
            border-radius: 999px;
            padding: 0.2rem 0.55rem;
            border: 1px solid rgba(76, 152, 211, 0.18);
        }}
        .ag-card__value {{
            font-size: 1.75rem;
            line-height: 1.1;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }}
        .ag-card__body {{
            color: var(--muted);
            font-size: 0.95rem;
            line-height: 1.55;
        }}
        .ag-card__body[data-tooltip] {{
            position: relative;
            cursor: help;
        }}
        .ag-card__body[data-tooltip]:hover::after {{
            content: attr(data-tooltip);
            position: absolute;
            bottom: calc(100% + 12px);
            left: -10px;
            width: 260px;
            background: rgba(15, 29, 39, 0.98);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 1.2rem;
            border-radius: 12px;
            font-size: 0.88rem;
            line-height: 1.5;
            box-shadow: 0 16px 32px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.05);
            z-index: 9999;
            opacity: 0;
            pointer-events: none;
            transform: translateY(10px);
            transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
            backdrop-filter: blur(8px);
        }}
        .ag-card__body[data-tooltip]:hover::before {{
            content: '';
            position: absolute;
            bottom: calc(100% + 4px);
            left: 15px;
            border-width: 8px;
            border-style: solid;
            border-color: var(--border) transparent transparent transparent;
            z-index: 10000;
            opacity: 0;
            pointer-events: none;
            transform: translateY(10px);
            transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        }}
        .ag-card__body[data-tooltip]:hover::after,
        .ag-card__body[data-tooltip]:hover::before {{
            opacity: 1;
            transform: translateY(0);
        }}
        .ag-card__action {{
            margin-top: 0.8rem;
            padding: 0.7rem 0.85rem;
            border-radius: 14px;
            background: var(--accent-soft);
            color: var(--text);
            font-size: 0.9rem;
            border: 1px solid rgba(216, 162, 74, 0.16);
        }}
        .ag-hero {{
            border-radius: 24px;
            padding: 1.4rem;
            color: white;
            background: linear-gradient(135deg, var(--tone-start) 0%, var(--tone-end) 100%);
            box-shadow: 0 22px 44px rgba(0, 0, 0, 0.24);
            margin-bottom: 1rem;
        }}
        .ag-hero__eyebrow {{
            display: inline-flex;
            align-items: center;
            gap: 0.55rem;
            font-size: 0.84rem;
            letter-spacing: 0.02em;
            opacity: 0.92;
        }}
        .ag-hero__title {{
            margin-top: 0.9rem;
            font-size: 2.15rem;
            line-height: 1.05;
            font-weight: 700;
        }}
        .ag-hero__subtitle {{
            margin-top: 0.55rem;
            max-width: 780px;
            font-size: 1rem;
            line-height: 1.6;
            opacity: 0.95;
        }}
        .ag-section-head {{
            display: flex;
            align-items: center;
            gap: 0.7rem;
            margin: 1rem 0 0.6rem;
        }}
        .ag-section-head h3 {{
            margin: 0;
            font-size: 1.08rem;
        }}
        .ag-caption {{
            color: var(--muted);
            font-size: 0.9rem;
        }}
        .ag-icon {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 2.35rem;
            height: 2.35rem;
            border-radius: 14px;
            background: rgba(255, 255, 255, 0.12);
            border: 1px solid rgba(255, 255, 255, 0.16);
            flex-shrink: 0;
        }}
        .ag-icon--card {{
            background: rgba(47, 163, 138, 0.10);
            border: 1px solid rgba(47, 163, 138, 0.16);
            color: var(--icon-color);
        }}
        .ag-sidebar-title {{
            display: flex;
            align-items: center;
            gap: 0.7rem;
            margin-bottom: 0.7rem;
        }}
        .ag-spacer {{
            height: 0.8rem;
        }}
        .stButton > button {{
            border-radius: 14px;
            min-height: 2.8rem;
            border: 1px solid transparent;
            background: var(--brand);
            color: white;
            font-weight: 600;
        }}
        .stButton > button:hover {{
            background: var(--brand-dark);
            color: white;
            border-color: transparent;
        }}
        .stButton > button[kind="secondary"] {{
            background: rgba(15, 29, 39, 0.96);
            color: var(--text);
            border-color: var(--border);
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.45rem;
        }}
        .stTabs [data-baseweb="tab"] {{
            border-radius: 12px;
            border: 1px solid var(--border);
            background: rgba(19, 38, 50, 0.84);
            color: var(--text);
            padding-top: 10px;
            padding-bottom: 10px;
            padding-left: 10px;
            padding-right: 10px;
        }}
        .stTabs [data-baseweb="tab-panel"] {{
            padding-top: 1.5rem !important;
            padding-bottom: 1rem !important;
            padding-right: 1.5rem !important;
            padding-left: 1.5rem !important;
        }}
        .stTabs [aria-selected="true"] {{
            background: rgba(15, 29, 39, 0.98);
        }}
        
        .ag-hero__expand {{
    margin-top: 0.9rem;
}}
.ag-hero__expand summary {{
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    cursor: pointer;
    list-style: none;
    padding: 0.45rem 0.9rem;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.16);
    border: 1px solid rgba(255, 255, 255, 0.28);
    color: #FFFFFF;
    font-size: 0.85rem;
    font-weight: 600;
    transition: background 0.2s ease;
    user-select: none;
}}
.ag-hero__expand summary:hover {{
    background: rgba(255, 255, 255, 0.26);
}}
.ag-hero__expand summary::-webkit-details-marker {{
    display: none;
}}
.ag-hero__expand summary::after {{
    content: "▾";
    font-size: 0.75rem;
    transition: transform 0.2s ease;
}}
.ag-hero__expand[open] summary::after {{
    transform: rotate(180deg);
}}
.ag-hero__expand[open] summary .ag-hero__expand-label::before {{
    content: "Ver menos";
}}
.ag-hero__expand:not([open]) summary .ag-hero__expand-label::before {{
    content: "Ver más";
}}
.ag-hero__expand-content {{
    margin-top: 0.8rem;
    padding: 0.85rem 1rem;
    border-radius: 14px;
    background: rgba(0, 0, 0, 0.18);
    border: 1px solid rgba(255, 255, 255, 0.14);
    font-size: 0.95rem;
    line-height: 1.55;
    color: #FFFFFF;
    opacity: 0.96;
}}
        """
    )


def icon_svg(name: str, size: int = 20, color: str = "currentColor") -> str:
    """Render a simple line icon as inline SVG."""
    path = ICON_PATHS.get(name, ICON_PATHS["chart"])
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none">'
        f'<path d="{path}" stroke="{color}" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )
    return (
        f'<img src="data:image/svg+xml;utf8,{quote(svg)}" '
        f'width="{size}" height="{size}" alt="" aria-hidden="true" />'
    )


def render_sidebar_brand(title: str, caption: str, *, icon: str = "sun", icon_color: str | None = None) -> None:
    """Render the sidebar brand block with escaped text."""
    brand_color = icon_color or PALETTE["brand"]
    render_html_block(
        f"""
        <div class="ag-sidebar-title">
            <span class="ag-icon ag-icon--card" style="--icon-color: {brand_color};">
                {icon_svg(icon, 18, brand_color)}
            </span>
            <div>
                <div style="font-weight:700;">{escape(title)}</div>
                <div class="ag-caption">{escape(caption)}</div>
            </div>
        </div>
        """
    )


def render_spacer() -> None:
    """Render a small vertical spacer without ad hoc inline HTML."""
    render_html_block('<div class="ag-spacer"></div>')


def render_section_header(title: str, icon: str = "chart", caption: str | None = None) -> None:
    """Render a compact section heading."""
    caption_html = f'<div class="ag-caption">{escape(caption)}</div>' if caption else ""
    render_html_block(
        f"""
        <div class="ag-section-head">
            <div class="ag-icon ag-icon--card" style="--icon-color: {PALETTE["brand"]};">
                {icon_svg(icon, 18, PALETTE["brand"])}
            </div>
            <div>
                <h3>{escape(title)}</h3>
                {caption_html}
            </div>
        </div>
        """
    )


def render_hero(
    title: str,
    subtitle: str = "",
    *,
    icon: str = "sun",
    eyebrow: str = "",
    tone: str = "brand",
    expandable_text: str | None = None,
) -> None:
    """Render the main page hero, con desglose opcional integrado."""
    tone_start, tone_end = TONE_MAP.get(tone, TONE_MAP["brand"])

    expand_html = ""
    if expandable_text:
        expand_html = f"""
            <details class="ag-hero__expand">
                <summary><span class="ag-hero__expand-label"></span></summary>
                <div class="ag-hero__expand-content">{escape(expandable_text)}</div>
            </details>
        """

    render_html_block(
        f"""
        <div class="ag-hero" style="--tone-start: {tone_start}; --tone-end: {tone_end};">
            <div class="ag-hero__eyebrow">
                <span class="ag-icon">{icon_svg(icon, 18, "#FFFFFF")}</span>
                <span>{escape(eyebrow)}</span>
            </div>
            <div class="ag-hero__title">{escape(title)}</div>
            <div class="ag-hero__subtitle">{escape(subtitle)}</div>
            {expand_html}
        </div>
        """
    )


def render_card(
    title: str,
    *,
    value: str = "",
    body: str = "",
    icon: str = "chart",
    tone: str = "brand",
    badge: str | None = None,
    action: str | None = None,
    tooltip: str | None = None,
) -> None:
    """Render a dashboard-style summary card."""
    color = TONE_MAP.get(tone, TONE_MAP["brand"])[0]
    badge_html = f'<span class="ag-card__badge">{escape(badge)}</span>' if badge else ""
    value_html = f'<div class="ag-card__value" style="color: {color};">{escape(value)}</div>' if value else ""
    
    tooltip_attr = f' data-tooltip="{escape(tooltip)}"' if tooltip else ""
    body_html = f'<div class="ag-card__body"{tooltip_attr}>{escape(body)}</div>' if body else ""
    
    action_html = f'<div class="ag-card__action">{escape(action)}</div>' if action else ""
    render_html_block(
        f"""
        <div class="ag-card">
            <div class="ag-card__top">
                <div class="ag-card__title">{escape(title)}</div>
                <div class="ag-icon ag-icon--card" style="--icon-color: {color};">
                    {icon_svg(icon, 18, color)}
                </div>
            </div>
            {badge_html}
            {value_html}
            {body_html}
            {action_html}
        </div>
        """
    )
