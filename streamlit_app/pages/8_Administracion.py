"""Pagina de administracion para usuarios admin."""

import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import api_get, api_patch, api_post, get_current_user, is_authenticated
from design import render_hero, render_section_header
from registro import render_registro
from ubicacion import CIUDAD
from ui import render_user_sidebar


st.set_page_config(page_title="Administracion", layout="wide", initial_sidebar_state="auto")
render_user_sidebar()

if not is_authenticated():
    st.warning("Debe iniciar sesion primero.")
    st.stop()

user = get_current_user() or {}
if user.get("role") != "admin":
    st.error("Acceso restringido. Solo usuarios con rol admin pueden acceder.")
    st.stop()

render_hero(
    "Administracion del sistema",
    "Gestion de usuarios, empresas y configuracion operativa.",
    icon="settings",
    eyebrow="Panel administrativo",
    tone="info",
)

tab_users, tab_empresas, tab_nuevo = st.tabs(["Usuarios", "Empresas", "Directorio"])

with tab_users:
    render_section_header("Usuarios registrados", "person", "Directorio de cuentas activas en la plataforma.")
    usuarios = api_get("/users/")
    if usuarios:
        show_users_table = st.toggle("Desplegar tabla de usuarios", key="users_toggle")
        if show_users_table:
            df = pd.DataFrame(usuarios)
            st.dataframe(df[["id", "email", "full_name", "role", "is_active", "empresa_id", "created_at"]], use_container_width=True, hide_index=True)

        st.markdown("<br>", unsafe_allow_html=True)
        render_section_header("Estado de Cuenta", "settings", "Suspende o reactiva los perfiles de acceso.")
        col_a, col_b, col_c = st.columns([2, 1, 1])
        with col_a:
            user_id = st.selectbox(
                "ID de Usuario",
                options=[u["id"] for u in usuarios],
                format_func=lambda item: next(f"{u['email']} ({'activo' if u['is_active'] else 'inactivo'})" for u in usuarios if u["id"] == item),
            )
        with col_b:
            if st.button("Activar"):
                if api_patch(f"/users/{user_id}/activate"):
                    st.success("Usuario activado.")
                    st.rerun()
        with col_c:
            if st.button("Desactivar"):
                if api_patch(f"/users/{user_id}/deactivate"):
                    st.success("Usuario desactivado.")
                    st.rerun()

with tab_empresas:
    render_section_header("Empresas asociadas", "factory", "Clientes corporativos con sistemas solares registrados.")
    empresas = api_get("/empresas/")
    if empresas:
        show_em_table = st.toggle("Desplegar tabla de empresas", key="empresas_toggle")
        if show_em_table:
            st.dataframe(pd.DataFrame(empresas), use_container_width=True, hide_index=True)
        else:
             st.caption("👈 Activa este interruptor para examinar la tabla JSON de infraestructura.")

with tab_nuevo:
    render_section_header("Gestión de Entidades", "spark", "Alta de nuevas cuentas y clientes corporativos.")
    sub_t0, sub_t1, sub_t2 = st.tabs(["Registrar hogar o negocio", "Alta Empresa", "Alta Usuario"])

    with sub_t0:
        # Cuenta nueva con su hogar o negocio y sus aparatos (antes era el registro público)
        render_registro()

    with sub_t1:
        with st.form("form_empresa"):
            col_a, col_b = st.columns(2)
            with col_a:
                nombre = st.text_input("Nombre*")
                tipo = st.selectbox("Tipo", ["hotel", "hielera", "retail", "pyme", "comunidad", "otro"])
                direccion = st.text_input("Direccion")
                tarifa = st.number_input("Tarifa (COP/kWh)", min_value=0.0, value=943.0, step=10.0)
            with col_b:
                ciudad = st.text_input("Ciudad", value=CIUDAD)
                departamento = st.text_input("Departamento", value="La Guajira")
                paneles = st.number_input("Capacidad paneles (kW)", min_value=0.0, value=0.0, step=0.5)
                bateria = st.number_input("Capacidad bateria (kWh)", min_value=0.0, value=0.0, step=0.5)

            if st.form_submit_button("Crear empresa", type="primary"):
                if nombre:
                    payload = {
                        "nombre": nombre,
                        "tipo": tipo,
                        "direccion": direccion,
                        "ciudad": ciudad,
                        "departamento": departamento,
                        "tarifa_kwh": tarifa,
                        "capacidad_paneles_kw": paneles,
                        "capacidad_bateria_kwh": bateria,
                    }
                    response = api_post("/empresas/", json=payload)
                    if response:
                        st.success(f"Empresa creada: ID {response['id']}")
                        st.rerun()
                else:
                    st.warning("El nombre es requerido.")

    with sub_t2:
        empresas_disp = api_get("/empresas/") or []
        with st.form("form_user"):
            col_a, col_b = st.columns(2)
            with col_a:
                email = st.text_input("Email*")
                password = st.text_input("Contrasena*", type="password")
                full_name = st.text_input("Nombre completo*")
            with col_b:
                role = st.selectbox("Rol", ["admin", "empresa", "analista"])
                empresa_id = None
                if role == "empresa" and empresas_disp:
                    opciones = {f"{e['nombre']} (ID:{e['id']})": e["id"] for e in empresas_disp}
                    st.markdown("**Empresa asociada**")
                    seleccion = st.selectbox(
                        "Empresa asociada",
                        list(opciones.keys()),
                        label_visibility="collapsed",
                    )
                    empresa_id = opciones[seleccion]

            if st.form_submit_button("Crear usuario", type="primary"):
                if email and password and full_name:
                    payload = {
                        "email": email,
                        "password": password,
                        "full_name": full_name,
                        "role": role,
                        "empresa_id": empresa_id,
                    }
                    response = api_post("/auth/register", json=payload)
                    if response:
                        st.success(f"Usuario creado: ID {response['id']}")
                        st.rerun()
                else:
                    st.warning("Completa todos los campos requeridos.")
