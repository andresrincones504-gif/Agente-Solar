"""Shared Streamlit UI helpers."""

from __future__ import annotations

import os
import sys
from html import escape

import streamlit as st

from api_client import (
    ROLES_CON_SELECTOR_ESCENARIO,
    api_get,
    get_active_scenario,
    get_current_user,
    is_authenticated,
    logout,
)
from design import icon_svg, inject_css, inject_style_block, render_html_block, PALETTE


PAGE_VISIBILITY = {
    "Home": {"roles": ("empresa", "admin", "analista")},
    "Mi_Dia": {"roles": ("empresa", "admin")},
    "Mis_Aparatos": {"roles": ("empresa", "admin", "analista")},
    "Dashboard": {"roles": ("admin", "empresa", "analista")},
    "Consumo": {"roles": ("admin", "empresa", "analista")},
    "Datos_Solares": {"roles": ("admin", "analista")},
    "Recomendaciones_IA": {"roles": ("admin", "empresa", "analista")},
    "Alertas": {"roles": ("admin", "empresa", "analista")},
    "Predicciones": {"roles": ("admin", "empresa", "analista")},
    "Reportes": {"roles": ("admin", "analista", "empresa")},
    "Administracion": {"roles": ("admin",)},
}

# Menú lateral: (clave, archivo, nombre visible), en el orden en que se muestran.
# Cada rol ve solo las pantallas que tiene permitidas (PAGE_VISIBILITY).
NAV_ITEMS = (
    ("Home", "Home.py", "Inicio"),
    ("Mi_Dia", "pages/0_Mi_Dia.py", "Mi día"),
    ("Mis_Aparatos", "pages/0_Mis_Aparatos.py", "Mis Aparatos"),
    ("Dashboard", "pages/1_Dashboard.py", "Panel"),
    ("Consumo", "pages/2_Consumo.py", "Consumo"),
    ("Recomendaciones_IA", "pages/4_Recomendaciones_IA.py", "Recomendaciones IA"),
    ("Alertas", "pages/5_Alertas.py", "Alertas"),
    ("Predicciones", "pages/6_Predicciones.py", "Predicciones"),
    ("Reportes", "pages/7_Reportes.py", "Reportes"),
    ("Datos_Solares", "pages/3_Datos_Solares.py", "Datos solares"),
    ("Administracion", "pages/8_Administracion.py", "Administración"),
)
NOMBRE_PAGINA = {clave: nombre for clave, _, nombre in NAV_ITEMS}


def puede_ver(clave: str, user: dict | None = None) -> bool:
    """True si el rol del usuario tiene acceso a esa pantalla."""
    role = (user or get_current_user() or {}).get("role", "empresa")
    return role in PAGE_VISIBILITY.get(clave, {}).get("roles", ())


def _hide_pages_by_user() -> None:
    """Hide sidebar pages based on user role only."""
    user = get_current_user() or {}
    role = user.get("role", "empresa")

    hidden = [key for key, cfg in PAGE_VISIBILITY.items() if role not in cfg["roles"]]
    if not hidden:
        return

    selectors = []
    for key in hidden:
        selectors.append(f'[data-testid="stSidebarNav"] a[href*="{key}"]')
        selectors.append(f'[data-testid="stSidebarNav"] li:has(a[href*="{key}"])')

    inject_style_block(f"{', '.join(selectors)} {{ display: none !important; }}")


def _pagina_actual() -> str | None:
    """Clave de la pantalla que se está mostrando, para resaltarla en el menú."""
    ruta = getattr(sys.modules.get("__main__"), "__file__", "") or ""
    if not ruta:
        try:
            from streamlit.runtime.scriptrunner import get_script_run_ctx

            ctx = get_script_run_ctx()
            pagina = ctx.pages_manager.get_pages().get(ctx.page_script_hash, {}) if ctx else {}
            ruta = str(pagina.get("script_path", ""))
        except Exception:
            ruta = ""
    archivo = os.path.basename(ruta)
    for clave, path, _ in NAV_ITEMS:
        if os.path.basename(path) == archivo:
            return clave
    return None


def _etiqueta_seccion(user: dict) -> str:
    """Título pequeño sobre el menú: Hogar, Mi negocio, Administración o Análisis."""
    role = user.get("role")
    if role == "admin":
        return "Administración"
    if role == "analista":
        return "Análisis"
    empresa_id = user.get("empresa_id")
    if not empresa_id:
        return "Mi espacio"
    tipos = st.session_state.setdefault("_tipo_empresa_menu", {})
    if empresa_id not in tipos:
        empresa = api_get(f"/empresas/{empresa_id}") or {}
        tipos[empresa_id] = empresa.get("tipo") or ""
    return "Hogar" if tipos[empresa_id] == "hogar" else "Mi negocio"


def _iniciales(nombre: str) -> str:
    partes = [p for p in (nombre or "").split() if p[:1].isalpha()]
    return ("".join(p[0] for p in partes[:2]) or "U").upper()


def _item_menu(clave: str, path: str, nombre: str, actual: str | None) -> None:
    if clave == actual:
        render_html_block(
            f'<div class="ag-nav-item ag-nav-item--activo" aria-current="page">'
            f'<span class="ag-nav-dot"></span><span>{escape(nombre)}</span></div>'
        )
    else:
        st.page_link(path, label=nombre)


def render_menu(user: dict) -> None:
    """Menú de pantallas según el rol, todas a la vista."""
    actual = _pagina_actual()
    with st.container():
        render_html_block(f'<div class="ag-nav-label">{escape(_etiqueta_seccion(user))}</div>')
        for clave, path, nombre in NAV_ITEMS:
            if puede_ver(clave, user):
                _item_menu(clave, path, nombre, actual)


def render_escenario(user) -> None:
    """Escenario activo en la barra lateral. Admin y analista pueden cambiarlo."""
    escenario_actual = get_active_scenario()
    if user and user.get("role") in ROLES_CON_SELECTOR_ESCENARIO:
        # Pasan de la empresa demo a las empresas reales sin cambiar de cuenta
        opciones = ["demo", "real"]
        elegido = st.radio(
            "Escenario",
            opciones,
            index=opciones.index(escenario_actual),
            format_func=lambda e: "Demo" if e == "demo" else "Real",
            horizontal=True,
            key="selector_escenario",
            help="Demo muestra el hotel de ejemplo; Real, las empresas registradas.",
        )
        if elegido != escenario_actual:
            st.session_state["escenario_activo"] = elegido
            st.rerun()
    else:
        escenario_label = "Demo" if escenario_actual == "demo" else "Real"
        st.caption(f"Escenario activo: **{escenario_label}**")


def go_to_login() -> None:
    """Send the user back to Home/login."""
    st.switch_page("Home.py")


def render_sidebar_autenticado(user: dict | None) -> None:
    """Barra lateral completa: menú arriba; marca, usuario y cierre de sesión abajo."""
    user = user or {}
    # El menú automático de Streamlit queda oculto desde design.inject_css
    with st.sidebar:
        render_menu(user)

        with st.container():
            render_html_block(
                f"""
                <div class="ag-side-bottom">
                    <div class="ag-side-brand">
                        <span class="ag-side-brand__icon">{icon_svg("sun", 18, PALETTE["brand"])}</span>
                        <div>
                            <div class="ag-side-brand__name">Ka’i</div>
                            <div class="ag-side-brand__caption">Operación diaria simplificada</div>
                        </div>
                    </div>
                </div>
                """
            )
            nombre = user.get("full_name", "Usuario")
            correo = user.get("email", "")
            correo_html = f'<div class="ag-user-card__mail">{escape(correo)}</div>' if correo else ""
            render_html_block(
                f"""
                <div class="ag-user-card">
                    <span class="ag-user-card__avatar">{escape(_iniciales(nombre))}</span>
                    <div class="ag-user-card__text">
                        <div class="ag-user-card__name">{escape(nombre)}</div>
                        {correo_html}
                    </div>
                </div>
                """
            )
            render_escenario(user)
            if st.button("Cerrar sesión", use_container_width=True, key="sidebar_logout"):
                logout()
                go_to_login()


def render_user_sidebar() -> None:
    """Render the authenticated sidebar."""
    if not is_authenticated():
        go_to_login()

    inject_css()
    _hide_pages_by_user()
    render_sidebar_autenticado(get_current_user())
