"""Shared Streamlit UI helpers."""

import streamlit as st

from api_client import (
    ROLES_CON_SELECTOR_ESCENARIO,
    get_active_scenario,
    get_current_user,
    is_authenticated,
    logout,
)
from design import inject_css, inject_style_block, render_sidebar_brand


PAGE_VISIBILITY = {
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


def render_user_sidebar() -> None:
    """Render the authenticated sidebar."""
    if not is_authenticated():
        go_to_login()

    inject_css()
    _hide_pages_by_user()

    with st.sidebar:
        render_sidebar_brand("Agente Solar", "Operacion diaria simplificada")

        user = get_current_user()
        if user:
            st.success(user.get("full_name", "Usuario"))
        render_escenario(user)

        st.divider()
        if st.button("Cerrar sesion", use_container_width=True, key="sidebar_logout"):
            logout()
            go_to_login()
