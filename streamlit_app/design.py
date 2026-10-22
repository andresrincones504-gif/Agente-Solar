"""Shared design system for the Streamlit app."""

from __future__ import annotations

import json
from html import escape
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components


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

# Hero "sólido" (prototipo Mi día): color plano con un leve degradado
TONE_SOLIDO = {
    "brand": ("#2A9580", "#1F7767"),
    "info": ("#3E83BA", "#2F6896"),
    "success": ("#2E9C6E", "#237D58"),
    "warning": ("#C99A30", "#B58623"),
    "danger": ("#B9554C", "#9A433B"),
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


def _fijar_css_en_pagina(css: str) -> None:
    """Copia los estilos al <head> de la página para que sigan puestos al cambiar de pantalla.

    Al cambiar de pantalla Streamlit borra todo lo de la pantalla anterior antes de dibujar
    la nueva, incluidos los <style> que van como elemento. Durante ese instante la app se
    veía sin estilos (otro fondo, el menú por defecto) y luego "saltaba". La copia en <head>
    no la toca Streamlit, así que el fondo y el menú se quedan quietos entre pantallas.
    """
    components.html(
        "<script>"
        "const doc = window.parent.document;"
        "doc.documentElement.lang = 'es';"
        "let tag = doc.getElementById('kai-estilos');"
        "if (!tag) { tag = doc.createElement('style'); tag.id = 'kai-estilos'; doc.head.appendChild(tag); }"
        f"const css = {json.dumps(css)};"
        "if (tag.textContent !== css) { tag.textContent = css; }"
        # En celular el menú lateral tapa la pantalla: se cierra solo al cambiar de pantalla
        "const win = window.parent;"
        "const ruta = win.location.pathname;"
        "if (win.__kaiRuta !== ruta) {"
        "  win.__kaiRuta = ruta;"
        "  if (win.innerWidth < 768) {"
        "    setTimeout(() => {"
        "      const abierto = doc.querySelector('[data-testid=\"stSidebar\"][aria-expanded=\"true\"]');"
        "      const boton = doc.querySelector('[data-testid=\"stSidebarCollapseButton\"] button');"
        "      if (abierto && boton) { boton.click(); }"
        "    }, 350);"
        "  }"
        "}"
        "</script>",
        height=0,
    )


def inject_css() -> None:
    """Inject global design tokens and component styles."""
    css = (
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
            position: relative;
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
        
/* El texto completo del hero aparece en una ventana flotante al pasar el mouse */
.ag-hero__panel {{
    position: absolute;
    inset: 0;
    z-index: 2;
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
    padding: 0.8rem 1.2rem 0.8rem;
    border-radius: 24px;
    background: rgba(15, 29, 39, 0.97);
    border: 1px solid var(--border);
    box-shadow: 0 16px 32px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(8px);
    color: var(--text);
    overflow-y: auto;
    scrollbar-width: none;
    opacity: 0;
    visibility: hidden;
    pointer-events: none;
    transform: scale(0.985);
    transition: opacity 0.2s ease, transform 0.2s ease, visibility 0.2s ease;
}}
.ag-hero:hover .ag-hero__panel,
.ag-hero:focus-within .ag-hero__panel {{
    opacity: 1;
    visibility: visible;
    pointer-events: auto;
    transform: none;
}}
.ag-hero--solido .ag-hero__panel {{
    border-radius: 16px;
}}
/* Sin barra de desplazamiento visible: el texto ocupa justo el recuadro */
.ag-hero__panel::-webkit-scrollbar {{
    display: none;
}}
.ag-hero__panel-head {{
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding-right: 0;
    font-size: 1.02rem;
    font-weight: 700;
    color: var(--text);
}}
.ag-hero__panel-head .ag-icon {{
    width: 1.8rem;
    height: 1.8rem;
    border-radius: 50%;
    background: rgba(216, 162, 74, 0.14);
    border: 1px solid rgba(216, 162, 74, 0.4);
}}
.ag-hero__panel-body {{
    font-size: 0.93rem;
    line-height: 1.5;
    text-align: justify;
    text-justify: inter-word;
    color: #D5E1E7;
}}

/* ---------- Menú lateral (prototipo Ka'i) ---------- */
[data-testid="stSidebar"][aria-expanded="true"] {{
    width: 264px !important;
    min-width: 264px !important;
    max-width: 264px !important;
}}
[data-testid="stSidebarContent"] {{
    display: flex;
    flex-direction: column;
}}
[data-testid="stSidebarUserContent"] {{
    flex: 1 0 auto;
    display: flex;
    flex-direction: column;
    padding: 0 1rem 1.25rem;
}}
[data-testid="stSidebarUserContent"] > div,
[data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlockBorderWrapper"] > div {{
    flex: 1 0 auto;
    display: flex;
    flex-direction: column;
}}
[data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"] {{
    flex: 1 0 auto;
}}
[data-testid="stVerticalBlock"]:has(> [data-testid="element-container"] .ag-nav-label) {{
    gap: 0.2rem;
}}
.ag-nav-label {{
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
    padding: 0 0.8rem 0.6rem;
}}
.ag-nav-item {{
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.45rem 0.8rem;
    border-radius: 10px;
    border: 1px solid transparent;
    font-size: 0.92rem;
    line-height: 1.35;
    color: var(--text);
}}
.ag-nav-item--activo {{
    background: rgba(47, 163, 138, 0.12);
    border: 1px solid rgba(47, 163, 138, 0.5);
    font-weight: 600;
    box-shadow: inset 0 0 18px rgba(47, 163, 138, 0.10);
}}
.ag-nav-dot {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--success);
    box-shadow: 0 0 0 3px rgba(57, 185, 130, 0.18);
    flex-shrink: 0;
}}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {{
    padding: 0.45rem 0.8rem;
    line-height: 1.35;
    margin: 0;
    border-radius: 10px;
    border: 1px solid transparent;
}}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {{
    background: rgba(234, 242, 246, 0.05);
}}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] p,
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] span {{
    font-size: 0.92rem;
    line-height: 1.35;
    margin: 0;
    color: #C5D3DA;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-side-bottom) {{
    margin-top: auto;
    padding-top: 1.5rem;
}}
[data-testid="stVerticalBlock"]:has(> [data-testid="element-container"] .ag-side-bottom) {{
    gap: 0.75rem;
}}
.ag-side-bottom {{
    border-top: 1px solid var(--border);
    padding-top: 1rem;
}}
.ag-side-brand {{
    display: flex;
    align-items: center;
    gap: 0.7rem;
}}
.ag-side-brand__icon {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.2rem;
    height: 2.2rem;
    border-radius: 10px;
    background: rgba(47, 163, 138, 0.10);
    border: 1px solid rgba(47, 163, 138, 0.35);
    flex-shrink: 0;
}}
.ag-side-brand__name {{
    font-weight: 700;
    font-size: 0.98rem;
    color: var(--text);
}}
.ag-side-brand__caption {{
    font-size: 0.8rem;
    color: var(--muted);
    line-height: 1.3;
}}
.ag-user-card {{
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding: 0.65rem 0.75rem;
    border-radius: 12px;
    background: rgba(47, 163, 138, 0.08);
    border: 1px solid rgba(47, 163, 138, 0.35);
}}
.ag-user-card__avatar {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    border: 1px solid rgba(47, 163, 138, 0.6);
    background: rgba(47, 163, 138, 0.14);
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--text);
    flex-shrink: 0;
    overflow: hidden;
    white-space: nowrap;
}}
.ag-user-card__text {{
    min-width: 0;
}}
.ag-user-card__name {{
    font-weight: 600;
    font-size: 0.92rem;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.ag-user-card__mail {{
    font-size: 0.76rem;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
[data-testid="stVerticalBlock"]:has(> [data-testid="element-container"] .ag-side-bottom) .stButton button {{
    background: #9B2C2C;
    border: 1px solid #9B2C2C;
    color: #FFFFFF;
    border-radius: 10px;
    min-height: 2.6rem;
}}
[data-testid="stVerticalBlock"]:has(> [data-testid="element-container"] .ag-side-bottom) .stButton button:hover {{
    background: #B23A3A;
    border-color: #B23A3A;
    color: #FFFFFF;
}}

/* ---------- Mi día (prototipo) ---------- */
.ag-hero--solido {{
    border-radius: 16px;
    padding: 2.1rem 1.6rem 2.2rem;
    box-shadow: 0 16px 36px rgba(0, 0, 0, 0.22);
}}
.ag-hero--solido .ag-hero__eyebrow .ag-icon {{
    width: 1.6rem;
    height: 1.6rem;
    border-radius: 50%;
}}
.ag-hero--solido .ag-hero__title {{
    margin-top: 0.7rem;
    font-size: 1.75rem;
}}
.ag-hero--solido .ag-hero__subtitle {{
    font-size: 0.98rem;
    max-width: 860px;
}}
.ag-icon--round {{
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
}}
.ag-tile__top {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.8rem;
    margin-bottom: 0.55rem;
}}
.ag-tile__title {{
    font-size: 0.98rem;
    font-weight: 700;
    line-height: 1.35;
    color: var(--text);
}}
.ag-tile__body {{
    color: var(--muted);
    font-size: 0.92rem;
    line-height: 1.55;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-tile) {{
    background: linear-gradient(180deg, rgba(16, 31, 41, 0.96), rgba(12, 24, 33, 0.96));
    border: 1px solid var(--border) !important;
    border-radius: 14px !important;
    padding: 1.1rem 1.15rem 1.15rem !important;
    height: 100%;
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.18);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-tile) > div {{
    height: 100%;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-tile) > div > [data-testid="stVerticalBlock"] {{
    height: 100%;
    gap: 0.9rem;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-tile) > div > [data-testid="stVerticalBlock"] > [data-testid="element-container"]:has(.stButton) {{
    margin-top: auto;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-tile) .stButton button {{
    background: #47535B;
    border: 1px solid #47535B;
    color: #FFFFFF;
    border-radius: 8px;
    min-height: 2.45rem;
    font-weight: 600;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-tile) .stButton button:hover {{
    background: var(--brand-dark);
    border-color: var(--brand-dark);
    color: #FFFFFF;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-tile) .stButton button p {{
    font-size: 0.88rem;
}}
[data-testid="column"]:has(.ag-tile) > [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="column"]:has(.ag-tile) > [data-testid="stVerticalBlockBorderWrapper"] > div,
[data-testid="column"]:has(.ag-tile) > [data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"] {{
    height: 100%;
}}

/* ---------- Tablas de solo lectura (Mis aparatos) ---------- */
.ag-tabla-titulo {{
    margin: 0.4rem 0 0.55rem;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
}}
.ag-tabla-wrap {{
    margin-bottom: 1.4rem;
    border: 1px solid var(--border);
    border-radius: 14px;
    background: linear-gradient(180deg, rgba(16, 31, 41, 0.7), rgba(12, 24, 33, 0.7));
    overflow-x: auto;
}}
.ag-tabla {{
    width: 100%;
    min-width: 760px;
    border-collapse: collapse;
    font-size: 0.93rem;
    color: var(--text);
}}
.ag-tabla--tipos {{
    min-width: 420px;
}}
.ag-tabla th {{
    padding: 0.9rem 1.1rem;
    border-bottom: 1px solid var(--border);
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    text-align: left;
    color: var(--muted);
    white-space: nowrap;
}}
.ag-tabla td {{
    padding: 0.8rem 1.1rem;
    border-bottom: 1px solid rgba(33, 58, 73, 0.55);
    vertical-align: middle;
}}
.ag-tabla tbody tr:last-child td {{
    border-bottom: none;
}}
.ag-tabla tbody tr:hover td {{
    background: rgba(234, 242, 246, 0.03);
}}
.ag-tabla__nombre {{
    min-width: 13rem;
    font-weight: 500;
}}
.ag-tabla .ag-tabla__centro {{
    text-align: center;
}}
.ag-tabla .ag-tabla__derecha {{
    text-align: right;
}}
.ag-tabla__num {{
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-variant-numeric: tabular-nums;
    font-weight: 700;
    white-space: nowrap;
}}
.ag-tabla__cantidad {{
    display: inline-block;
    min-width: 2.6rem;
    padding: 0.25rem 0.6rem;
    border-radius: 8px;
    background: rgba(234, 242, 246, 0.06);
    font-variant-numeric: tabular-nums;
}}
.ag-tabla__pct {{
    display: flex;
    align-items: center;
    gap: 0.65rem;
    min-width: 9rem;
}}
.ag-tabla__barra {{
    flex: 1;
    height: 6px;
    border-radius: 999px;
    background: rgba(234, 242, 246, 0.08);
    overflow: hidden;
}}
.ag-tabla__barra > span {{
    display: block;
    height: 100%;
    border-radius: 999px;
    background: var(--brand);
}}
.ag-tabla__pct .ag-tabla__num {{
    min-width: 3.4rem;
    text-align: right;
    font-weight: 600;
    font-size: 0.86rem;
}}
.ag-pill {{
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 8px;
    border: 1px solid transparent;
    font-size: 0.78rem;
    font-weight: 600;
    white-space: nowrap;
}}
.ag-pill--tipico {{
    background: rgba(47, 163, 138, 0.12);
    border-color: rgba(47, 163, 138, 0.38);
    color: #5CC9AE;
}}
.ag-pill--tuyo {{
    background: rgba(216, 162, 74, 0.12);
    border-color: rgba(216, 162, 74, 0.38);
    color: #E3B866;
}}
.ag-pill--factura {{
    background: rgba(76, 152, 211, 0.12);
    border-color: rgba(76, 152, 211, 0.38);
    color: #7DB6E3;
}}
.ag-tabla__pie {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem 1.5rem;
    padding: 0.9rem 1.1rem;
    border-top: 1px solid var(--border);
    font-size: 0.9rem;
    color: var(--muted);
}}
.ag-tabla__resumen {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem 1.4rem;
}}
.ag-tabla__resumen b {{
    color: var(--text);
}}
.ag-tabla__total {{
    display: flex;
    align-items: center;
    gap: 0.7rem;
}}
.ag-tabla__total-valor {{
    padding: 0.45rem 0.85rem;
    border-radius: 10px;
    border: 1px solid rgba(57, 185, 130, 0.45);
    background: rgba(57, 185, 130, 0.10);
    color: var(--success);
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-weight: 700;
    white-space: nowrap;
}}

/* ---------- Tabla para editar aparatos (tonos cálidos de la marca: dorado y azul) ---------- */
.ag-pill--info {{
    background: rgba(76, 152, 211, 0.12);
    border-color: rgba(76, 152, 211, 0.38);
    color: #7DB6E3;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-edit-pie) {{
    padding: 0 !important;
    border: 1px solid rgba(216, 162, 74, 0.28) !important;
    border-radius: 14px !important;
    background: linear-gradient(180deg, rgba(19, 38, 50, 0.75), rgba(15, 29, 39, 0.9));
    overflow: hidden;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-edit-pie) > div > [data-testid="stVerticalBlock"] {{
    gap: 0;
}}
[data-testid="stHorizontalBlock"]:has(.ag-edit-th) {{
    padding: 0.75rem 1rem;
    background: rgba(48, 38, 26, 0.9);
    border-bottom: 1px solid rgba(216, 162, 74, 0.3);
}}
[data-testid="stHorizontalBlock"]:has(.ag-edit-td) {{
    padding: 0.45rem 1rem;
    border-bottom: 1px solid rgba(216, 162, 74, 0.12);
    transition: background 0.15s ease;
}}
[data-testid="stHorizontalBlock"]:has(.ag-edit-td):hover {{
    background: rgba(216, 162, 74, 0.05);
}}
.ag-edit-th {{
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--accent);
    white-space: nowrap;
}}
.ag-edit-td {{
    font-size: 0.93rem;
    color: var(--text);
}}
.ag-edit-td--nombre {{
    font-weight: 500;
}}
.ag-edit-td--centro {{
    text-align: center;
}}
.ag-edit-td--derecha {{
    text-align: right;
}}
.ag-edit-num {{
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-variant-numeric: tabular-nums;
    font-weight: 700;
    white-space: nowrap;
}}
.ag-edit-num small {{
    font-family: inherit;
    font-weight: 400;
    color: var(--muted);
}}
.ag-edit-chip {{
    display: inline-block;
    min-width: 2.4rem;
    padding: 0.2rem 0.6rem;
    border-radius: 8px;
    border: 1px solid rgba(216, 162, 74, 0.35);
    background: rgba(216, 162, 74, 0.12);
    color: #E3B866;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
}}
/* Botones de editar (azul) y eliminar (rojo suave) */
[data-testid="stHorizontalBlock"]:has(.ag-edit-td) .stButton {{
    display: flex;
    justify-content: center;
}}
[data-testid="stHorizontalBlock"]:has(.ag-edit-td) .stButton button {{
    width: 2.4rem;
    min-height: 2.2rem;
    height: 2.2rem;
    padding: 0;
    border-radius: 8px;
    background: transparent;
    border: 1px solid rgba(76, 152, 211, 0.4);
    color: #7DB6E3;
}}
[data-testid="stHorizontalBlock"]:has(.ag-edit-td) .stButton button:hover {{
    background: rgba(76, 152, 211, 0.15);
    border-color: #4C98D3;
    color: #A9CFEE;
}}
[data-testid="stHorizontalBlock"]:has(.ag-edit-td) [data-testid="stHorizontalBlock"] > [data-testid="column"]:last-child .stButton button {{
    border-color: rgba(212, 106, 96, 0.45);
    color: var(--danger);
}}
[data-testid="stHorizontalBlock"]:has(.ag-edit-td) [data-testid="stHorizontalBlock"] > [data-testid="column"]:last-child .stButton button:hover {{
    background: rgba(212, 106, 96, 0.15);
    border-color: var(--danger);
    color: #EE958C;
}}
.ag-edit-pie {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem 1.5rem;
    padding: 0.9rem 1.1rem;
    background: rgba(48, 38, 26, 0.45);
    font-size: 0.9rem;
    color: var(--muted);
}}
.ag-edit-pie__resumen {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem 1.4rem;
}}
.ag-edit-pie__resumen b {{
    color: var(--text);
}}
.ag-edit-pie__total {{
    display: flex;
    align-items: center;
    gap: 0.7rem;
}}
.ag-edit-pie__valor {{
    padding: 0.45rem 0.85rem;
    border-radius: 10px;
    border: 1px solid rgba(216, 162, 74, 0.5);
    background: rgba(216, 162, 74, 0.12);
    color: #E3B866;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-weight: 700;
    white-space: nowrap;
}}
/* Ventanas de editar y eliminar */
.ag-dialogo-nota {{
    margin: 0.3rem 0 0.6rem;
    padding: 0.6rem 0.8rem;
    border-radius: 10px;
    border: 1px solid rgba(216, 162, 74, 0.3);
    background: rgba(216, 162, 74, 0.08);
    color: var(--text);
}}
.ag-dialogo-borrar {{
    font-size: 1rem;
    line-height: 1.5;
}}
div[role="dialog"]:has(.ag-dialogo-borrar) .stButton button[kind="primary"] {{
    background: var(--danger);
    border-color: var(--danger);
}}
div[role="dialog"]:has(.ag-dialogo-borrar) .stButton button[kind="primary"]:hover {{
    background: #B9554C;
    border-color: #B9554C;
}}

/* ---------- Agregar aparatos: catálogo por categorías ---------- */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) {{
    padding: 1.4rem 1.6rem !important;
    border: 1px solid var(--border) !important;
    border-radius: 14px !important;
    background: linear-gradient(180deg, rgba(16, 31, 41, 0.92), rgba(12, 24, 33, 0.92));
}}
.ag-add-caption {{
    font-size: 0.85rem;
    color: var(--muted);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpander"] {{
    --cat-color: var(--muted);
    --cat-fondo: rgba(154, 176, 187, 0.12);
    --cat-borde: rgba(154, 176, 187, 0.4);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpander"]:has(.ag-cat--refrigeracion) {{
    --cat-color: #39B982;
    --cat-fondo: rgba(57, 185, 130, 0.12);
    --cat-borde: rgba(57, 185, 130, 0.4);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpander"]:has(.ag-cat--climatizacion) {{
    --cat-color: #7DB6E3;
    --cat-fondo: rgba(76, 152, 211, 0.12);
    --cat-borde: rgba(76, 152, 211, 0.4);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpander"]:has(.ag-cat--iluminacion) {{
    --cat-color: #E3B866;
    --cat-fondo: rgba(216, 162, 74, 0.12);
    --cat-borde: rgba(216, 162, 74, 0.4);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpander"]:has(.ag-cat--cocina) {{
    --cat-color: #D9A441;
    --cat-fondo: rgba(217, 164, 65, 0.12);
    --cat-borde: rgba(217, 164, 65, 0.4);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpander"]:has(.ag-cat--lavado) {{
    --cat-color: #7DB6E3;
    --cat-fondo: rgba(76, 152, 211, 0.12);
    --cat-borde: rgba(76, 152, 211, 0.4);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpander"]:has(.ag-cat--entretenimiento) {{
    --cat-color: #5CC9AE;
    --cat-fondo: rgba(47, 163, 138, 0.12);
    --cat-borde: rgba(47, 163, 138, 0.4);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpander"]:has(.ag-cat--cuidado_personal) {{
    --cat-color: #E08A80;
    --cat-fondo: rgba(212, 106, 96, 0.12);
    --cat-borde: rgba(212, 106, 96, 0.4);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpander"]:has(.ag-cat--oficina) {{
    --cat-color: #7DB6E3;
    --cat-fondo: rgba(76, 152, 211, 0.12);
    --cat-borde: rgba(76, 152, 211, 0.4);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpander"]:has(.ag-cat--bombas_motores) {{
    --cat-color: #B5C6CE;
    --cat-fondo: rgba(154, 176, 187, 0.12);
    --cat-borde: rgba(154, 176, 187, 0.4);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpander"] details {{
    border: 1px solid var(--border);
    border-radius: 12px;
    background: rgba(15, 29, 39, 0.65);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpander"] summary {{
    padding: 0.75rem 0.9rem;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpander"] summary:hover [data-testid="stExpanderToggleIcon"] {{
    border-color: var(--cat-borde);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpander"] summary strong {{
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--text);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpander"] summary p span.has-background-color {{
    margin-left: 0.6rem;
    padding: 0.12rem 0.6rem !important;
    border-radius: 999px;
    border: 1px solid var(--cat-borde);
    background-color: var(--cat-fondo) !important;
    color: var(--cat-color);
    font-size: 0.75rem;
    font-weight: 600;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpanderToggleIcon"] {{
    width: 1.9rem;
    height: 1.9rem;
    padding: 0.3rem;
    border-radius: 8px;
    border: 1px solid var(--border);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpanderDetails"] {{
    padding: 0 0.9rem 0.3rem;
    border-top: 1px solid var(--border);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpanderDetails"] [data-testid="stVerticalBlock"] {{
    gap: 0;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="element-container"]:has(> [data-testid="stHtml"] > .ag-cat) {{
    display: none;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpanderDetails"] [data-testid="element-container"]:has([data-testid="stCheckbox"]) {{
    padding: 0.65rem 0;
    border-bottom: 1px solid rgba(33, 58, 73, 0.6);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stExpanderDetails"] [data-testid="element-container"]:has([data-testid="stCheckbox"]):last-child {{
    border-bottom: none;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stCheckbox"] label {{
    width: 100%;
    align-items: flex-start;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stCheckbox"] label > div:last-child {{
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stCheckbox"] [data-testid="stWidgetLabel"],
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stCheckbox"] [data-testid="stWidgetLabel"] [data-testid="stMarkdownContainer"] {{
    flex: 1 1 auto;
    width: 100%;
    max-width: none;
    min-width: 0;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stCheckbox"] [data-testid="stWidgetLabel"] p {{
    font-size: 0.95rem;
    line-height: 1.35;
    color: var(--text);
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stCheckbox"] [data-testid="stWidgetLabel"] p > span {{
    display: block;
    margin-top: 0.1rem;
    font-size: 0.82rem;
    color: var(--muted) !important;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .ag-add-caption) [data-testid="stCheckbox"] [data-testid="stTooltipIcon"] {{
    color: var(--muted);
}}

/* ---------- Responsive: tablets y celulares ---------- */
/* El área de contenido es un "contenedor": las filas se reacomodan según el espacio real
   (con o sin menú lateral abierto), no solo según el ancho de la pantalla. */
[data-testid="stAppViewBlockContainer"] {{
    container-type: inline-size;
    container-name: kai-main;
}}
/* En pantallas táctiles el resumen del hero se abre con un toque */
.ag-hero[tabindex]:focus {{
    outline: none;
}}
@media (hover: none) {{
    .ag-hero[tabindex] {{
        cursor: pointer;
    }}
}}
/* Filas de 3 o más tarjetas: dos por línea cuando el espacio es mediano, una cuando es angosto */
@container kai-main (max-width: 760px) {{
    [data-testid="stHorizontalBlock"]:has(> [data-testid="column"]:nth-child(3)):not(:has(.ag-edit-td)):not(:has(.ag-edit-th)):not([data-testid="column"] [data-testid="stHorizontalBlock"]) {{
        flex-wrap: wrap;
        row-gap: 1rem;
    }}
    [data-testid="stHorizontalBlock"]:has(> [data-testid="column"]:nth-child(3)):not(:has(.ag-edit-td)):not(:has(.ag-edit-th)):not([data-testid="column"] [data-testid="stHorizontalBlock"]) > [data-testid="column"] {{
        flex: 1 1 calc(50% - 1rem) !important;
        min-width: calc(50% - 1rem) !important;
    }}
    /* Tabla para editar aparatos: cada aparato como una tarjeta con sus etiquetas */
    [data-testid="stHorizontalBlock"]:has(.ag-edit-th) {{
        display: none;
    }}
    [data-testid="stHorizontalBlock"]:has(.ag-edit-td) {{
        flex-wrap: wrap;
        gap: 0.6rem 0.9rem;
        padding: 0.85rem 1rem;
    }}
    [data-testid="stHorizontalBlock"]:has(.ag-edit-td) > [data-testid="column"] {{
        flex: 1 1 calc(33% - 0.9rem) !important;
        min-width: calc(33% - 0.9rem) !important;
        width: auto !important;
    }}
    [data-testid="stHorizontalBlock"]:has(.ag-edit-td) > [data-testid="column"]:first-child,
    [data-testid="stHorizontalBlock"]:has(.ag-edit-td) > [data-testid="column"]:last-child {{
        flex-basis: 100% !important;
        min-width: 100% !important;
    }}
    .ag-edit-td {{
        text-align: left !important;
    }}
    .ag-edit-td--nombre {{
        font-weight: 700;
    }}
    .ag-edit-td[data-label]::before {{
        content: attr(data-label);
        display: block;
        margin-bottom: 0.2rem;
        font-family: "Source Sans Pro", sans-serif;
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--accent);
    }}
    [data-testid="stHorizontalBlock"]:has(.ag-edit-td) [data-testid="stHorizontalBlock"] {{
        flex-wrap: nowrap;
        gap: 0.6rem;
    }}
    [data-testid="stHorizontalBlock"]:has(.ag-edit-td) [data-testid="stHorizontalBlock"] > [data-testid="column"] {{
        flex: 0 0 auto !important;
        min-width: 0 !important;
        width: auto !important;
    }}
    [data-testid="stHorizontalBlock"]:has(.ag-edit-td) .stButton {{
        justify-content: flex-start;
    }}
    .ag-edit-pie,
    .ag-tabla__pie {{
        flex-direction: column;
        align-items: flex-start;
    }}
}}
@container kai-main (max-width: 520px) {{
    [data-testid="stHorizontalBlock"]:has(> [data-testid="column"]:nth-child(3)):not(:has(.ag-edit-td)):not(:has(.ag-edit-th)):not([data-testid="column"] [data-testid="stHorizontalBlock"]) > [data-testid="column"] {{
        flex-basis: 100% !important;
        min-width: 100% !important;
    }}
}}
@media (max-width: 1024px) {{
    [data-testid="stAppViewBlockContainer"] {{
        padding-left: 1.5rem;
        padding-right: 1.5rem;
    }}
    .ag-hero__title {{
        font-size: 1.8rem;
    }}
}}
@media (max-width: 640px) {{
    [data-testid="stAppViewBlockContainer"] {{
        padding-left: 1rem;
        padding-right: 1rem;
    }}
    .ag-hero {{
        padding: 1.1rem;
        border-radius: 18px;
    }}
    .ag-hero--solido {{
        padding: 1.4rem 1.1rem 1.5rem;
    }}
    .ag-hero__title,
    .ag-hero--solido .ag-hero__title {{
        font-size: 1.45rem;
    }}
    .ag-hero__subtitle {{
        font-size: 0.93rem;
    }}
    /* En celular el resumen completo no cabe en el recuadro: se desliza con el dedo */
    .ag-hero__panel {{
        scrollbar-width: thin;
        -webkit-overflow-scrolling: touch;
    }}
    .ag-hero__panel::-webkit-scrollbar {{
        display: block;
        width: 4px;
    }}
    .ag-hero__panel::-webkit-scrollbar-thumb {{
        background: var(--border);
        border-radius: 4px;
    }}
    .ag-hero__panel-body {{
        font-size: 0.88rem;
        text-align: left;
    }}
    .ag-section-head h3 {{
        font-size: 1rem;
    }}
    .ag-card {{
        padding: 0.9rem;
    }}
    .ag-card__body[data-tooltip]:hover::after {{
        width: min(260px, calc(100vw - 4rem));
    }}
    [data-testid="stMetricValue"] {{
        font-size: 1.25rem;
    }}
    .ag-welcome,
    .ag-note {{
        padding: 1rem 1.1rem;
    }}
}}

/* ---------- Cambio de pantalla suave ---------- */
/* El menú automático de Streamlit se reemplaza por el propio (ui.render_menu) */
[data-testid="stSidebarNav"] {{
    display: none !important;
}}
/* El iframe que fija los estilos no ocupa espacio */
[data-testid="element-container"]:has(> iframe[title="st.iframe"][height="0"]) {{
    position: absolute !important;
    width: 0 !important;
    height: 0 !important;
    overflow: hidden !important;
    margin: 0 !important;
}}
@keyframes kaiAparecer {{
    from {{ opacity: 0; transform: translateY(6px); }}
    to {{ opacity: 1; transform: none; }}
}}
@keyframes kaiAparecerSuave {{
    from {{ opacity: 0; }}
    to {{ opacity: 1; }}
}}
[data-testid="stAppViewBlockContainer"] > [data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"] > * {{
    animation: kaiAparecer 0.35s ease-out both;
}}
[data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"] > * {{
    animation: kaiAparecerSuave 0.25s ease-out both;
}}
@media (prefers-reduced-motion: reduce) {{
    [data-testid="stAppViewBlockContainer"] *,
    [data-testid="stSidebarUserContent"] * {{
        animation: none !important;
    }}
}}
        """
    )
    inject_style_block(css)
    _fijar_css_en_pagina(css)


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


def render_section_header(
    title: str, icon: str = "chart", caption: str | None = None, *, round_icon: bool = False
) -> None:
    """Render a compact section heading."""
    caption_html = f'<div class="ag-caption">{escape(caption)}</div>' if caption else ""
    icon_class = "ag-icon ag-icon--card ag-icon--round" if round_icon else "ag-icon ag-icon--card"
    render_html_block(
        f"""
        <div class="ag-section-head">
            <div class="{icon_class}" style="--icon-color: {PALETTE["brand"]};">
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
    variant: str = "degradado",
    expandable_title: str = "Resumen completo",
) -> None:
    """Render the main page hero, con desglose opcional integrado.

    variant="solido" usa el color plano del prototipo de Mi día.
    """
    solido = variant == "solido"
    tonos = TONE_SOLIDO if solido else TONE_MAP
    tone_start, tone_end = tonos.get(tone, tonos["brand"])
    hero_class = "ag-hero ag-hero--solido" if solido else "ag-hero"

    expand_html = ""
    # Con resumen flotante el hero acepta foco: en celular se abre con un toque
    tabindex = ' tabindex="0"' if expandable_text else ""
    if expandable_text:
        expand_html = f"""
            <div class="ag-hero__panel" role="tooltip" aria-label="{escape(expandable_title)}">
                <div class="ag-hero__panel-head">
                    <span class="ag-icon">{icon_svg(icon, 16, PALETTE["accent"])}</span>
                    <span>{escape(expandable_title)}</span>
                </div>
                <div class="ag-hero__panel-body">{escape(expandable_text)}</div>
            </div>
        """

    render_html_block(
        f"""
        <div class="{hero_class}"{tabindex} style="--tone-start: {tone_start}; --tone-end: {tone_end};">
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
    badge_tinted: bool = False,
) -> None:
    """Render a dashboard-style summary card.

    badge_tinted=True pinta la etiqueta con el color del tono de la tarjeta.
    """
    color = TONE_MAP.get(tone, TONE_MAP["brand"])[0]
    badge_style = f' style="background: {color}1F; border-color: {color}59; color: {color};"' if badge_tinted else ""
    badge_html = f'<span class="ag-card__badge"{badge_style}>{escape(badge)}</span>' if badge else ""
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


def render_tile(title: str, body: str = "", *, icon: str = "chart", tone: str = "brand") -> None:
    """Contenido de una tarjeta del prototipo: título, ícono redondo y texto.

    Va dentro de st.container(border=True); la clase .ag-tile le da el estilo al
    contenedor y deja el botón que se ponga debajo pegado al fondo de la tarjeta.
    """
    color = TONE_MAP.get(tone, TONE_MAP["brand"])[0]
    body_html = f'<div class="ag-tile__body">{escape(body)}</div>' if body else ""
    render_html_block(
        f"""
        <div class="ag-tile">
            <div class="ag-tile__top">
                <div class="ag-tile__title">{escape(title)}</div>
                <span class="ag-icon ag-icon--card ag-icon--round"
                      style="--icon-color: {color}; background: {color}1F; border-color: {color}66;">
                    {icon_svg(icon, 16, color)}
                </span>
            </div>
            {body_html}
        </div>
        """
    )


# Colores del logo de Ka'i (un poco más vivos que los de la interfaz)
LOGO_DORADO = "#F9B11A"
LOGO_VERDE = "#17A398"

_LOGO_ANILLO = (
    "M56 24H64V32H72V40H80V48H88V56H96V64H88V72H80V80H72V88H64V96H56V88H48V80H40V72H32V64H24V56H32V48H40V40H48V32H56Z "
    "M56 32H64V40H72V48H80V56H88V64H80V72H72V80H64V88H56V80H48V72H40V64H32V56H40V48H48V40H56Z"
)
_LOGO_NUCLEO = "M56 40H64V48H72V56H80V64H72V72H64V80H56V72H48V64H40V56H48V48H56Z"
_LOGO_RAYOS = ((56, 8), (56, 104), (8, 56), (104, 56), (24, 24), (88, 24), (24, 88), (88, 88))


def logo_kai_html(icon_px: int = 118) -> str:
    """Logo de Ka'i: sol tejido (cuadros, estilo wayuu) + palabra Ka'i con el apóstrofo dorado."""
    rayos = "".join(f'<rect x="{x}" y="{y}" width="8" height="8"/>' for x, y in _LOGO_RAYOS)
    # El dibujo va de 8 a 112: se recorta el borde vacío para que el logo quede centrado de verdad
    lado = round(icon_px * 104 / 120)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="8 8 104 104" width="{lado}" height="{lado}">'
        f'<path fill="{LOGO_VERDE}" fill-rule="evenodd" d="{_LOGO_ANILLO}"/>'
        f'<path fill="{LOGO_DORADO}" d="{_LOGO_NUCLEO}"/>'
        f'<rect x="56" y="56" width="8" height="8" fill="{PALETTE["bg"]}"/>'
        f'<g fill="{LOGO_DORADO}">{rayos}</g>'
        "</svg>"
    )
    # Como imagen (igual que icon_svg): st.html no deja pasar <svg> en línea
    icono = (
        f'<img src="data:image/svg+xml;utf8,{quote(svg)}" width="{lado}" height="{lado}" alt="Sol de Ka’i" />'
    )
    tam_letra = round(icon_px * 0.72)
    palabra = (
        f'<span class="notranslate" translate="no" style="font-family: \'Outfit\', \'Century Gothic\', \'Segoe UI\', sans-serif; '
        f'font-weight: 700; font-size: {tam_letra}px; line-height: 1; letter-spacing: -0.02em; color: #FFFFFF;">'
        f'Ka<span style="color: {LOGO_DORADO};">’</span>i</span>'
    )
    return icono + palabra
