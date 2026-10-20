"""Agente Solar Inteligente - landing, login and registration."""

import streamlit as st

from api_client import (
    api_get,
    get_current_user,
    is_authenticated,
    login,
    logout,
    register,
)
from design import (
    inject_css,
    inject_style_block,
    render_card,
    render_hero,
    render_section_header,
    render_sidebar_brand,
    render_spacer,
)
from registro import render_registro
from ubicacion import CIUDAD
from ui import _hide_pages_by_user, go_to_login, render_escenario


# Mensajes del motor de recomendaciones según su estado (ver GET /ia/status)
MENSAJES_ASISTENTE = {
    "con_ia": {
        "titulo": "Tu asistente inteligente está en línea",
        "texto": (
            "Estamos conectados a internet: revisamos tu consumo, tus aparatos y el pronóstico "
            "del sol para darte consejos pensados para ti."
        ),
        "badge": "🟢 Conectado",
        "tono": "success",
        "icono": "spark",
    },
    "sin_conexion": {
        "titulo": "Sin internet por ahora, pero seguimos ayudándote",
        "texto": (
            "No logramos conectarnos con el asistente inteligente. Mientras vuelve la conexión, "
            "tus consejos salen de reglas basadas en tus aparatos y tu consumo, así que puedes seguir usándolos."
        ),
        "badge": "🟡 Modo básico",
        "tono": "warning",
        "icono": "cloud",
    },
    "sin_clave": {
        "titulo": "Tus consejos están en modo básico",
        "texto": (
            "Calculamos tus consejos con reglas basadas en tus aparatos y tu consumo. "
            "Cuando se active el asistente inteligente serán aún más personalizados."
        ),
        "badge": "Modo básico",
        "tono": "info",
        "icono": "idea",
    },
    "sin_respuesta": {
        "titulo": "No pudimos revisar tu asistente",
        "texto": "La aplicación no respondió en este momento. Intenta de nuevo en unos minutos.",
        "badge": None,
        "tono": "danger",
        "icono": "alert",
    },
}


def _pedir_revision_asistente() -> None:
    st.session_state["ia_revisar"] = True


def render_estado_asistente(user: dict) -> None:
    """Estado del motor de recomendaciones en palabras simples, con acciones para el usuario."""
    revisar = st.session_state.pop("ia_revisar", False)
    ia_status = api_get("/ia/status", params={"refrescar": "true"} if revisar else None)
    if ia_status is None:
        estado = "sin_respuesta"
    else:
        estado = ia_status.get("estado") or ("con_ia" if ia_status.get("gemini_disponible") else "sin_clave")
    mensaje = MENSAJES_ASISTENTE[estado]

    if revisar:
        st.toast("Listo, ya revisamos la conexión." if estado != "sin_conexion" else "Todavía no hay conexión. Seguimos en modo básico.")

    render_card(
        mensaje["titulo"],
        body=mensaje["texto"],
        badge=mensaje["badge"],
        icon=mensaje["icono"],
        tone=mensaje["tono"],
    )
    if estado == "sin_clave" and user.get("role") == "admin":
        st.caption("Solo lo ves como administrador: para activar el asistente inteligente falta poner la clave de Gemini (GEMINI_API_KEY) en el archivo .env.")

    acciones = st.columns(2)
    siguiente = 0
    if estado in ("sin_conexion", "sin_respuesta"):
        acciones[0].button("🔄 Revisar de nuevo", on_click=_pedir_revision_asistente, use_container_width=True, key="ia_revisar_btn")
        siguiente = 1
    if estado != "sin_respuesta" and acciones[siguiente].button(
        "Ver mis consejos →", type="primary", use_container_width=True, key="ia_ver_consejos"
    ):
        st.switch_page("pages/4_Recomendaciones_IA.py")


st.set_page_config(page_title="Agente Solar Inteligente", layout="wide", initial_sidebar_state="expanded")
inject_css()

if not is_authenticated():
    inject_style_block(
        """
        [data-testid="stSidebar"] { display: none; }
        [data-testid="collapsedControl"] { display: none; }
        """
    )
else:
    _hide_pages_by_user()

render_hero(
    "Agente Solar Inteligente",
    "Monitorea consumo, produccion solar, alertas y recomendaciones con una experiencia mas clara y menos cargada.",
    icon="sun",
    eyebrow=f"{CIUDAD} · gestion energetica asistida",
    tone="brand",
)

with st.sidebar:
    render_sidebar_brand("Agente Solar", "Acceso y navegacion")
    if is_authenticated():
        user = get_current_user()
        if user:
            st.success(user.get("full_name", "Usuario"))
            st.caption(user.get("email", ""))
        render_escenario(user)

        if st.button("Cerrar sesion", use_container_width=True):
            logout()
            go_to_login()
    else:
        st.info("Inicia sesion para continuar.")

if not is_authenticated():
    modo = st.radio(
        "Acceso",
        ["Iniciar sesión", "Crear una cuenta"],
        horizontal=True,
        key="home_modo",
        label_visibility="collapsed",
    )

if not is_authenticated() and modo == "Crear una cuenta":
    col_reg, col_porque = st.columns([2.2, 1])
    with col_reg:
        render_registro()
    with col_porque:
        render_card(
            "¿Por qué te preguntamos por tus aparatos?",
            body=(
                "Con tu lista de aparatos estimamos cuánto consume cada uno, "
                "y las alertas y recomendaciones te hablan de tus propios equipos: "
                "qué encender, cuándo hacerlo y cuál pesa más en tu factura."
            ),
            icon="idea",
            tone="success",
        )
        render_card(
            "¿No sabes la potencia?",
            body="No pasa nada. Deja el campo vacío y usamos un valor típico para ese aparato.",
            icon="bolt",
            tone="info",
        )
elif not is_authenticated():
    col_login, col_info = st.columns([1, 1.15])

    with col_login:
        render_section_header("Iniciar sesion", "lock", "Acceso para administracion, analisis y operacion.")
        with st.form("login_form"):
            email = st.text_input("Correo electronico", placeholder="usuario@empresa.com", key="login_email")
            password = st.text_input("Contrasena", type="password", key="login_pass")
            submit = st.form_submit_button("Ingresar", use_container_width=True)

            if submit:
                if email and password:
                    token = login(email, password)
                    if token:
                        st.success("Sesion iniciada correctamente.")
                        st.rerun()
                else:
                    st.warning("Completa ambos campos.")

        with st.expander("Credenciales de demostracion"):
            st.code(
                "Admin:\n"
                "  email: admin@agentesolar.co\n"
                "  password: admin123\n\n"
                "Empresa Demo:\n"
                "  email: hotel@agentesolar.co\n"
                "  password: hotel123"
            )

    with col_info:
        render_section_header("Resumen del sistema", "dashboard", "Vista general del producto.")
        cards = st.columns(2)
        with cards[0]:
            render_card(
                "Monitoreo operativo",
                body="KPIs, consumo, costos y estado energetico diario con una lectura rapida.",
                icon="chart",
                tone="info",
            )
        with cards[1]:
            render_card(
                "Inteligencia aplicada",
                body="Recomendaciones, predicciones y alertas construidas sobre datos solares y consumo.",
                icon="idea",
                tone="success",
            )
        cards = st.columns(2)
        with cards[0]:
            render_card(
                "Fuentes de datos",
                body="Open-Meteo, NASA POWER, OpenWeather y PVGIS para radiacion, clima y validacion.",
                icon="cloud",
                tone="warning",
            )
        with cards[1]:
            render_card(
                "Casos de uso",
                body="Hoteles, retail, cadena de frio y otras operaciones con sensibilidad a costo y continuidad.",
                icon="factory",
                tone="brand",
            )
else:
    user = get_current_user() or {}
    st.success(f"Bienvenido, {user.get('full_name', 'usuario')}.")
    n_aparatos = st.session_state.pop("bienvenida_aparatos", None)
    if n_aparatos is not None:
        if n_aparatos:
            st.info(f"Tu cuenta quedó creada con {n_aparatos} aparatos registrados.")
        else:
            st.info("Tu cuenta quedó creada. Cuando quieras, agrega tus aparatos para recibir consejos más precisos.")

    cols = st.columns(3)
    with cols[0]:
        render_card("Dashboard", body="Consulta KPIs, tendencias y comparativas del negocio.", icon="chart", tone="info")
    with cols[1]:
        render_card("Recomendaciones", body="Prioriza acciones concretas de ahorro y operacion.", icon="idea", tone="success")
    with cols[2]:
        render_card("Reportes", body="Descarga informes listos para seguimiento interno.", icon="report", tone="brand")

    render_spacer()
    st.info("Usa el menu lateral para navegar. Cada modulo inicia en vista compacta y permite abrir detalles tecnicos cuando los necesites.")

    status_cols = st.columns(2)
    with status_cols[0]:
        render_section_header("Motor de recomendaciones", "idea")
        render_estado_asistente(user)

    with status_cols[1]:
        render_section_header("Empresas accesibles", "factory")
        empresas = api_get("/empresas/")
        if empresas is not None:
            st.metric("Total", len(empresas))
            for empresa in empresas[:3]:
                st.caption(f"{empresa['nombre']} · {empresa.get('tipo', 'N/A')}")
