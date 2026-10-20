"""
Cliente HTTP para consumir la API FastAPI desde Streamlit.
"""

import os
from typing import Any, Dict, List, Optional

import requests
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_PREFIX = "/api/v1"


def _get_headers() -> Dict[str, str]:
    token = st.session_state.get("token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _clear_session() -> None:
    for key in ("token", "user", "escenario_activo"):
        if key in st.session_state:
            del st.session_state[key]


def _url(path: str) -> str:
    if path.startswith("http"):
        return path
    return f"{API_BASE_URL}{API_PREFIX}{path}"


# Roles que pueden cambiar entre la demo y los datos reales desde la barra lateral
ROLES_CON_SELECTOR_ESCENARIO = ("admin", "analista")


def get_active_scenario() -> str:
    user = get_current_user()
    elegido = st.session_state.get("escenario_activo")
    if user and user.get("role") in ROLES_CON_SELECTOR_ESCENARIO and elegido in ("demo", "real"):
        return elegido
    if user and "escenario_usuario" in user:
        return user["escenario_usuario"]
    value = st.session_state.get("escenario_activo", "demo")
    return value if value in ("demo", "real") else "demo"


def _with_scenario(params: Optional[Dict]) -> Dict:
    merged = dict(params or {})
    merged["escenario"] = get_active_scenario()
    return merged


def _detalle_error(resp: requests.Response) -> str:
    """Convierte el 'detail' de FastAPI (texto o lista de errores de validación) en un mensaje legible."""
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        return resp.text
    if isinstance(detail, list):
        mensajes = []
        for err in detail:
            if isinstance(err, dict):
                campo = ".".join(str(x) for x in err.get("loc", [])[1:])
                msg = str(err.get("msg", "")).replace("Value error, ", "")
                mensajes.append(f"{campo}: {msg}" if campo else msg)
            else:
                mensajes.append(str(err))
        return "; ".join(mensajes)
    if isinstance(detail, dict):
        return detail.get("mensaje") or str(detail)
    return str(detail)


@st.cache_data(ttl=600, show_spinner=False)
def get_catalogo_aparatos(categoria: Optional[str] = None) -> Optional[List[Dict]]:
    """Catálogo público de aparatos (no requiere sesión). None si la API no responde."""
    try:
        resp = requests.get(
            f"{API_BASE_URL}{API_PREFIX}/catalogo/aparatos",
            params={"categoria": categoria} if categoria else None,
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass
    return None


def login(email: str, password: str) -> Optional[str]:
    """Realiza login y retorna token. Guarda en session_state."""
    try:
        resp = requests.post(
            f"{API_BASE_URL}{API_PREFIX}/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            st.session_state["token"] = data["access_token"]
            me = api_get("/auth/me")
            if me:
                st.session_state["user"] = me
            return data["access_token"]

        try:
            detail = resp.json().get("detail", "Error desconocido")
        except Exception:
            detail = resp.text
        st.error(f"Login fallido: {detail}")
        return None
    except requests.RequestException as exc:
        st.error(f"Error de conexion con API: {exc}")
        return None


def register(
    email: str,
    password: str,
    full_name: str,
    role: str = "empresa",
    escenario_usuario: str = "real",
    nombre_empresa: Optional[str] = None,
    tipo_empresa: Optional[str] = None,
    tarifa_kwh: Optional[float] = None,
    tipo_entidad: Optional[str] = None,
    aparatos: Optional[List[Dict]] = None,
) -> bool:
    """Registra un nuevo usuario en la API."""
    try:
        payload = {
            "email": email,
            "password": password,
            "full_name": full_name,
            "role": role,
            "escenario_usuario": escenario_usuario,
            "nombre_empresa": nombre_empresa,
            "tipo_empresa": tipo_empresa,
            "tarifa_kwh": tarifa_kwh,
            "tipo_entidad": tipo_entidad,
            "aparatos": aparatos or [],
        }
        resp = requests.post(
            f"{API_BASE_URL}{API_PREFIX}/auth/register",
            json=payload,
            timeout=15,
        )
        if resp.status_code in (200, 201):
            return True

        st.error(f"Registro fallido: {_detalle_error(resp)}")
        return False
    except requests.RequestException as exc:
        st.error(f"Error de conexion con API: {exc}")
        return False


def logout(call_api: bool = True) -> bool:
    """
    Cierra sesion en el cliente y, si hay token, notifica a la API.

    La API actual valida el token en /auth/logout pero no revoca JWT emitidos
    previamente porque el esquema es stateless.
    """
    success = True
    token = st.session_state.get("token")

    if call_api and token:
        try:
            resp = requests.post(_url("/auth/logout"), headers=_get_headers(), timeout=10)
            success = resp.status_code in (200, 401)
        except requests.RequestException:
            success = False

    _clear_session()
    return success


def is_authenticated() -> bool:
    return "token" in st.session_state and st.session_state.get("token")


def get_current_user() -> Optional[Dict]:
    return st.session_state.get("user")


def api_get(path: str, params: Optional[Dict] = None) -> Optional[Any]:
    try:
        resp = requests.get(_url(path), headers=_get_headers(), params=_with_scenario(params), timeout=30)
        if resp.status_code == 401:
            _clear_session()
            st.warning("Sesion expirada. Inicie sesion nuevamente.")
            return None
        if resp.status_code >= 400:
            return None
        return resp.json()
    except requests.RequestException as exc:
        st.error(f"Error API: {exc}")
        return None


def api_post(path: str, json: Optional[Dict] = None, files: Any = None, params: Optional[Dict] = None) -> Optional[Any]:
    try:
        resp = requests.post(
            _url(path),
            headers=_get_headers(),
            json=json if files is None else None,
            files=files,
            params=_with_scenario(params),
            timeout=120,
        )
        if resp.status_code == 401:
            _clear_session()
            st.warning("Sesion expirada.")
            return None
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            st.error(f"Error {resp.status_code}: {detail}")
            return None
        return resp.json()
    except requests.RequestException as exc:
        st.error(f"Error API: {exc}")
        return None


def api_patch(path: str, json: Optional[Dict] = None, params: Optional[Dict] = None) -> Optional[Any]:
    try:
        resp = requests.patch(
            _url(path),
            headers=_get_headers(),
            json=json,
            params=_with_scenario(params),
            timeout=30,
        )
        if resp.status_code == 401:
            _clear_session()
            st.warning("Sesion expirada.")
            return None
        if resp.status_code >= 400:
            return None
        return resp.json()
    except requests.RequestException as exc:
        st.error(f"Error API: {exc}")
        return None


def api_delete(path: str, params: Optional[Dict] = None) -> bool:
    """DELETE autenticado. True si la API confirmó el borrado."""
    try:
        resp = requests.delete(_url(path), headers=_get_headers(), params=_with_scenario(params), timeout=30)
        if resp.status_code == 401:
            _clear_session()
            st.warning("Sesion expirada.")
            return False
        if resp.status_code >= 400:
            st.error(f"Error {resp.status_code}: {_detalle_error(resp)}")
            return False
        return True
    except requests.RequestException as exc:
        st.error(f"Error API: {exc}")
        return False


def api_patch_detallado(path: str, json: Optional[Dict] = None) -> Optional[Any]:
    """PATCH que muestra el motivo cuando la API rechaza el cambio."""
    try:
        resp = requests.patch(_url(path), headers=_get_headers(), json=json, params=_with_scenario(None), timeout=30)
        if resp.status_code == 401:
            _clear_session()
            st.warning("Sesion expirada.")
            return None
        if resp.status_code >= 400:
            st.error(f"No se pudo guardar: {_detalle_error(resp)}")
            return None
        return resp.json()
    except requests.RequestException as exc:
        st.error(f"Error API: {exc}")
        return None


def api_download(path: str, params: Optional[Dict] = None) -> Optional[bytes]:
    """Descarga binaria (PDF/Excel)."""
    try:
        resp = requests.get(_url(path), headers=_get_headers(), params=_with_scenario(params), timeout=60)
        if resp.status_code == 401:
            _clear_session()
            st.warning("Sesion expirada.")
            return None
        if resp.status_code >= 400:
            return None
        return resp.content
    except requests.RequestException as exc:
        st.error(f"Error descarga: {exc}")
        return None
