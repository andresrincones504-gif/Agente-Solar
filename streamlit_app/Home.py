"""Ka’i - inicio de sesión y pantalla de inicio.

Al abrir la app solo aparece el inicio de sesión: las cuentas nuevas las crea un
administrador desde Administración (la API ya no acepta registros públicos).
"""

from html import escape

import streamlit as st

from api_client import (
    api_get,
    get_current_user,
    is_authenticated,
    login,
)
from design import (
    inject_css,
    inject_style_block,
    logo_kai_html,
    render_card,
    render_hero,
    render_html_block,
    render_section_header,
)
from ubicacion import CIUDAD
from ui import _hide_pages_by_user, render_sidebar_autenticado


# Mensajes del motor de recomendaciones según su estado (ver GET /ia/status)
MENSAJES_ASISTENTE = {
    "con_ia": {
        "titulo": "Tu asistente inteligente está en línea",
        "texto": (
            "Estamos conectados a internet: revisamos tu consumo, tus aparatos y el pronóstico "
            "del sol para darte consejos pensados para ti."
        ),
        "badge": "Conectado",
        "tono": "success",
        "icono": "spark",
    },
    "sin_conexion": {
        "titulo": "Sin internet por ahora, pero seguimos ayudándote",
        "texto": (
            "No logramos conectarnos con el asistente inteligente. Mientras vuelve la conexión, "
            "tus consejos salen de reglas basadas en tus aparatos y tu consumo, así que puedes seguir usándolos."
        ),
        "badge": "Modo básico",
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
        "tono": "brand",
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
        badge_tinted=True,
    )

    # Solo cuando no hay conexión se ofrece volver a revisar (los consejos están en el menú lateral)
    if estado in ("sin_conexion", "sin_respuesta"):
        st.button("🔄 Revisar de nuevo", on_click=_pedir_revision_asistente, key="ia_revisar_btn")


LOGIN_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@600;700&display=swap');
[data-testid="stSidebar"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="stHeader"],
[data-testid="stDecoration"] {
    display: none;
}
[data-testid="stAppViewBlockContainer"] {
    width: 100%;
    max-width: 480px;
    min-height: 100vh;
    min-height: 100dvh;
    margin: 0 auto;
    padding: clamp(1rem, 6vh, 3rem) 1rem;
    display: flex;
    flex-direction: column;
    justify-content: center;
    /* Si la tarjeta no cabe a lo alto (celular acostado), la página se desplaza en vez de cortarla */
    flex-shrink: 0;
}
[data-testid="stAppViewBlockContainer"] [data-testid="element-container"]:has(style) {
    display: none;
}
/* Si la ventana cambia de tamaño, nada queda más ancho que la pantalla */
[data-testid="stAppViewBlockContainer"] [data-testid="stVerticalBlock"],
[data-testid="stAppViewBlockContainer"] [data-testid="stForm"] {
    max-width: 100%;
}
/* Tarjeta del login: un tono más claro que el fondo */
[data-testid="stForm"] {
    border: 1px solid rgba(234, 242, 246, 0.04) !important;
    border-radius: 14px !important;
    /* El relleno se ajusta al alto y ancho de la pantalla */
    padding: clamp(1.75rem, 10vh, 5.2rem) clamp(1.25rem, 6vw, 2.7rem) !important;
    background: #111E28 !important;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
}
.kai-login-logo {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    /* Ajuste óptico: los rayos del sol pesan poco a la vista, así que el conjunto se corre un poco a la izquierda */
    transform: translateX(-0.3rem);
    margin-bottom: clamp(1.25rem, 5.9vh, 3rem);
}
/* El logo se achica en pantallas angostas o bajas */
.kai-login-logo img {
    width: max(49px, min(95px, 20.8vw, 11.3vh)) !important;
    height: auto !important;
}
.kai-login-logo > span {
    font-size: max(40px, min(79px, 17vw, 9.4vh)) !important;
}
[data-testid="stForm"] label p {
    font-size: 0.95rem;
    font-weight: 400;
    color: var(--text);
}
/* Campos y botones comparten exactamente el mismo alto, ancho, borde y esquinas */
[data-testid="stForm"] {
    --alto-campo: 3.25rem;
}
[data-testid="stForm"] [data-baseweb="input"] {
    box-sizing: border-box;
    height: var(--alto-campo);
    min-height: var(--alto-campo);
    border-radius: 6px;
    border: 1px solid #2A4556;
    background: #0C1820;
}
[data-testid="stForm"] [data-baseweb="input"] > div {
    height: 100%;
    background: #0C1820 !important;
    border-radius: 6px;
}
[data-testid="stForm"] [data-baseweb="input"] input {
    background: #0C1820 !important;
}
[data-testid="stFormSubmitButton"],
[data-testid="stFormSubmitButton"] button {
    width: 100%;
}
[data-testid="stFormSubmitButton"] button {
    box-sizing: border-box;
    height: var(--alto-campo);
    min-height: var(--alto-campo);
    border: 1px solid transparent;
    border-radius: 6px;
    color: #FFFFFF;
}
[data-testid="stFormSubmitButton"] button p {
    font-size: 1.08rem;
    font-weight: 500;
}
/* Ingresar (verde) */
[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"] {
    margin-top: 1.1rem;
    background: #38BB84;
}
[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"]:hover {
    background: #2FA374;
    color: #FFFFFF;
}
/* Ingresar con cuenta demo (azul pizarra) */
[data-testid="stFormSubmitButton"] button[kind="secondaryFormSubmit"] {
    margin-top: 0.75rem;
    background: #233A4A;
}
[data-testid="stFormSubmitButton"] button[kind="secondaryFormSubmit"]:hover {
    background: #2B4659;
    color: #FFFFFF;
}

/* ---------- Adaptación a distintas pantallas ---------- */
/* Celulares: la tarjeta ocupa casi todo el ancho */
@media (max-width: 480px) {
    [data-testid="stAppViewBlockContainer"] {
        padding-left: 0.75rem;
        padding-right: 0.75rem;
    }
    [data-testid="stForm"] {
        border-radius: 12px !important;
    }
    [data-testid="stFormSubmitButton"] button p {
        font-size: 1rem;
    }
}
/* Pantallas bajas (portátiles pequeños, celular acostado): todo más compacto */
@media (max-height: 640px) {
    [data-testid="stForm"] {
        --alto-campo: 2.9rem;
    }
    [data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"] {
        margin-top: 0.6rem;
    }
    [data-testid="stFormSubmitButton"] button[kind="secondaryFormSubmit"] {
        margin-top: 0.4rem;
    }
}
/* Pantallas grandes: la tarjeta crece un poco */
@media (min-width: 1800px) and (min-height: 1000px) {
    [data-testid="stAppViewBlockContainer"] {
        max-width: 540px;
    }
    [data-testid="stForm"] {
        --alto-campo: 3.6rem;
    }
}
"""

# Cuenta de demostración (sale del seed): el botón "Ingresar con cuenta demo" entra con ella
DEMO_EMAIL = "hotel@agentesolar.co"
DEMO_PASSWORD = "hotel123"


def render_login() -> None:
    """Pantalla de entrada: tarjeta centrada con el logo de Ka’i, el formulario y la cuenta demo."""
    inject_style_block(LOGIN_CSS)
    with st.form("login_form", border=False):
        render_html_block(f'<div class="kai-login-logo">{logo_kai_html(110)}</div>')
        email = st.text_input("Correo electrónico", placeholder="Tucorreo@gmail.com", key="login_email")
        password = st.text_input("Contraseña", type="password", placeholder="Tu contraseña", key="login_pass")
        submit = st.form_submit_button("Ingresar", type="primary", use_container_width=True)
        demo = st.form_submit_button("Ingresar con cuenta demo", use_container_width=True)
        if demo:
            if login(DEMO_EMAIL, DEMO_PASSWORD):
                st.rerun()
        elif submit:
            if email and password:
                if login(email, password):
                    st.success("Sesion iniciada correctamente.")
                    st.rerun()
            else:
                st.warning("Completa ambos campos.")


st.set_page_config(page_title="Ka’i", layout="wide", initial_sidebar_state="expanded")
inject_css()

if not is_authenticated():
    render_login()
    st.stop()

_hide_pages_by_user()

render_hero(
    "Ka’i",
    "Monitorea consumo, produccion solar, alertas y recomendaciones con una experiencia mas clara y menos cargada.",
    icon="sun",
    eyebrow=f"{CIUDAD} · gestion energetica asistida",
    tone="brand",
)

# Mismo menú lateral que el resto de pantallas
render_sidebar_autenticado(get_current_user())

HOME_CSS = """
.ag-welcome {
    padding: 1.4rem 1.5rem;
    border-radius: 14px;
    background: rgba(15, 31, 39, 0.95);
    border: 1px solid rgba(47, 163, 138, 0.28);
    color: var(--text);
    font-size: 1rem;
}
.ag-note {
    margin: 0.35rem 0 0.6rem;
    padding: 1rem 1.35rem;
    border-radius: 14px;
    background: rgba(19, 38, 52, 0.9);
    border: 1px solid #1F3B4C;
    color: #DCE7EC;
    font-size: 1rem;
    line-height: 1.5;
}
.ag-stat-card {
    height: 100%;
    box-sizing: border-box;
    padding: 1.4rem 1.6rem;
    border-radius: 20px;
    background: linear-gradient(180deg, rgba(16, 31, 41, 0.98), rgba(12, 24, 33, 0.98));
    border: 1px solid var(--border);
    box-shadow: 0 18px 40px rgba(0, 0, 0, 0.22);
    color: var(--text);
}
.ag-stat-card__label {
    color: var(--muted);
    font-size: 0.92rem;
}
.ag-stat-card__value {
    margin: 0.15rem 0 1rem;
    font-size: 2.6rem;
    font-weight: 700;
    line-height: 1.1;
}
.ag-stat-card__list {
    list-style: none;
    margin: 0;
    padding: 1rem 0 0;
    border-top: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}
.ag-stat-card__list li {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin: 0;
    font-size: 0.95rem;
}
.ag-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--success);
    flex-shrink: 0;
}
/* Tarjetas de una misma fila (las tres de arriba y las dos de abajo) del mismo alto */
[data-testid="stHorizontalBlock"]:is(:has(.ag-card), :has(.ag-stat-card)) > [data-testid="column"] > [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stHorizontalBlock"]:is(:has(.ag-card), :has(.ag-stat-card)) > [data-testid="column"] > [data-testid="stVerticalBlockBorderWrapper"] > div,
[data-testid="stHorizontalBlock"]:is(:has(.ag-card), :has(.ag-stat-card)) > [data-testid="column"] > [data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"] {
    height: 100%;
}
[data-testid="stHorizontalBlock"]:is(:has(.ag-card), :has(.ag-stat-card)) [data-testid="element-container"]:has(.ag-card),
[data-testid="stHorizontalBlock"]:is(:has(.ag-card), :has(.ag-stat-card)) [data-testid="element-container"]:has(.ag-stat-card) {
    flex: 1 1 auto;
}
[data-testid="stHorizontalBlock"]:is(:has(.ag-card), :has(.ag-stat-card)) [data-testid="element-container"]:has(.ag-card) > [data-testid="stHtml"],
[data-testid="stHorizontalBlock"]:is(:has(.ag-card), :has(.ag-stat-card)) [data-testid="element-container"]:has(.ag-stat-card) > [data-testid="stHtml"] {
    height: 100%;
}
"""
inject_style_block(HOME_CSS)

user = get_current_user() or {}
render_html_block(f'<div class="ag-welcome">Bienvenido, {escape(user.get("full_name", "usuario"))}.</div>')
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
    render_card("Reportes", body="Descarga informes listos para seguimiento interno.", icon="report", tone="warning")

render_html_block(
    '<div class="ag-note">Usa el menu lateral para navegar. Cada modulo inicia en vista compacta '
    "y permite abrir detalles tecnicos cuando los necesites.</div>"
)

status_cols = st.columns(2)
with status_cols[0]:
    render_section_header("Motor de recomendaciones", "idea")
    render_estado_asistente(user)

with status_cols[1]:
    render_section_header("Empresas accesibles", "factory")
    empresas = api_get("/empresas/")
    if empresas is not None:
        items = "".join(
            f'<li><span class="ag-dot"></span>{escape(e["nombre"])} · {escape(str(e.get("tipo", "N/A")))}</li>'
            for e in empresas[:3]
        )
        lista = f'<ul class="ag-stat-card__list">{items}</ul>' if items else ""
        render_html_block(
            f"""
            <div class="ag-stat-card">
                <div class="ag-stat-card__label">Total</div>
                <div class="ag-stat-card__value">{len(empresas)}</div>
                {lista}
            </div>
            """
        )
