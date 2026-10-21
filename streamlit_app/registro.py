"""
Registro de usuarios nuevos (solo administrador, desde Administración), en tres pasos:
1. Cuenta y tipo de entidad (hogar, negocio, empresa, institución, finca, comunidad).
2. Aparatos de esa categoría, con buscador por palabras y selección múltiple.
3. Cantidad, potencia (W) y horas de uso opcionales por aparato, y creación de la cuenta.

El estado vive en st.session_state con prefijo "reg_" para poder ir y volver entre pasos.
"""
from __future__ import annotations

import re
from itertools import groupby

import streamlit as st

from api_client import get_catalogo_aparatos, register
from design import render_section_header
from inventario import coincide

ENTIDADES = {
    "hogar": ("Hogar", "Casa o apartamento familiar"),
    "negocio": ("Negocio o comercio", "Tienda, restaurante, peluquería, panadería…"),
    "empresa": ("Empresa o industria", "Hotel, hielera, bodega, fábrica…"),
    "institucion": ("Institución", "Colegio, puesto de salud, oficina pública…"),
    "finca": ("Finca o actividad agropecuaria", "Ganadería, cultivos, ordeño, riego…"),
    "comunidad": ("Comunidad", "Junta de acción comunal o espacio comunitario"),
}
NOMBRE_ENTIDAD = {
    "hogar": ("Nombre de tu hogar", "Familia Pérez Losada"),
    "negocio": ("Nombre del negocio", "Tienda Doña Rosa"),
    "empresa": ("Nombre de la empresa", "Hotel Solar Fonseca"),
    "institucion": ("Nombre de la institución", "Institución Educativa Ana María Vélez"),
    "finca": ("Nombre de la finca", "Finca La Esperanza"),
    "comunidad": ("Nombre de la comunidad", "Junta de Acción Comunal Barrio Centro"),
}
GIROS = {
    "negocio": ["tienda", "restaurante", "peluquería", "panadería", "droguería", "taller", "otro"],
    "empresa": ["hotel", "hielera", "bodega", "industria", "retail", "otro"],
    "institucion": ["colegio", "puesto de salud", "oficina pública", "otro"],
    "finca": ["ganadera", "agrícola", "mixta"],
}
TIPOS_APARATO = {
    "refrigeracion": "Refrigeración",
    "climatizacion": "Aire y ventilación",
    "iluminacion": "Iluminación",
    "cocina": "Cocina",
    "lavado": "Lavado y planchado",
    "entretenimiento": "Entretenimiento",
    "cuidado_personal": "Cuidado personal",
    "oficina": "Oficina y tecnología",
    "bombas_motores": "Bombas, motores y herramientas",
}
PASOS = {1: "Cuenta", 2: "Aparatos", 3: "Cantidades y consumo"}


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------
def _estado() -> dict:
    ss = st.session_state
    ss.setdefault("reg_paso", 1)
    ss.setdefault("reg_datos", {"tipo_entidad": "hogar", "tarifa": 943.0})
    ss.setdefault("reg_sel", {})  # str(catalogo_id) -> {"cantidad", "potencia_w", "horas"}
    ss.setdefault("reg_propios", [])  # [{"nombre", "potencia_w", "horas", "cantidad"}]
    return ss


def _ir_a(paso: int) -> None:
    st.session_state["reg_paso"] = paso


def _limpiar_estado() -> None:
    for k in [k for k in st.session_state.keys() if str(k).startswith("reg_")]:
        del st.session_state[k]


def _kwh_mes(potencia_w: float, horas: float, cantidad: int = 1) -> float:
    return (potencia_w or 0) * (horas or 0) * (cantidad or 1) * 30 / 1000


def _indicador_pasos(paso: int) -> None:
    partes = []
    for n, nombre in PASOS.items():
        marca = "●" if n == paso else ("✓" if n < paso else "○")
        partes.append(f"**{marca} {n}. {nombre}**" if n == paso else f"{marca} {n}. {nombre}")
    st.markdown("  ·  ".join(partes))
    st.progress(paso / len(PASOS))


# ---------------------------------------------------------------------------
# Paso 1
# ---------------------------------------------------------------------------
def _paso_1(ss) -> None:
    datos = ss["reg_datos"]
    render_section_header("¿Qué vas a registrar?", "factory", "Con esto te mostramos solo los aparatos que aplican a tu caso.")
    claves = list(ENTIDADES)
    tipo = st.radio(
        "Tipo de entidad",
        options=claves,
        index=claves.index(datos.get("tipo_entidad", "hogar")),
        format_func=lambda k: ENTIDADES[k][0],
        captions=[ENTIDADES[k][1] for k in claves],
        horizontal=True,
        key="reg_tipo_entidad",
        label_visibility="collapsed",
    )

    render_section_header("Datos de la cuenta", "person", "Con este correo y contraseña la persona iniciará sesión.")
    c1, c2 = st.columns(2)
    nombre = c1.text_input("Nombre completo", value=datos.get("full_name", ""), placeholder="Juan Pérez", key="reg_full_name")
    email = c2.text_input("Correo electrónico", value=datos.get("email", ""), placeholder="juan.perez@correo.com", key="reg_email")
    c3, c4 = st.columns(2)
    password = c3.text_input("Contraseña", type="password", value=datos.get("password", ""), help="Mínimo 6 caracteres", key="reg_password")
    password2 = c4.text_input("Repite la contraseña", type="password", value=datos.get("password2", ""), key="reg_password2")

    etiqueta, ejemplo = NOMBRE_ENTIDAD[tipo]
    c5, c6 = st.columns(2)
    nombre_entidad = c5.text_input(etiqueta, value=datos.get("nombre_entidad", ""), placeholder=ejemplo, key="reg_nombre_entidad")
    tarifa = c6.number_input(
        "Tarifa de energía (COP/kWh)",
        min_value=100.0, max_value=5000.0, step=10.0,
        value=float(datos.get("tarifa", 943.0)),
        help="Está en tu recibo de luz como valor del kWh. En La Guajira ronda los $943.",
        key="reg_tarifa",
    )
    giro = None
    if tipo in GIROS:
        opciones = GIROS[tipo]
        previo = datos.get("giro") if datos.get("giro") in opciones else opciones[0]
        giro = st.selectbox("Actividad", opciones, index=opciones.index(previo), key="reg_giro")

    if st.button("Siguiente: elegir aparatos →", type="primary", use_container_width=True, key="reg_btn_1"):
        errores = []
        if len(nombre.strip()) < 3:
            errores.append("Escribe tu nombre completo.")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()):
            errores.append("El correo no parece válido.")
        if len(password) < 6:
            errores.append("La contraseña debe tener al menos 6 caracteres.")
        elif password != password2:
            errores.append("Las contraseñas no coinciden.")
        if len(nombre_entidad.strip()) < 2:
            errores.append(f"Escribe el {etiqueta.lower()}.")
        if errores:
            for e in errores:
                st.error(e)
            return
        if datos.get("tipo_entidad") != tipo:
            ss["reg_sel"] = {}  # cambió la categoría: la selección anterior puede no aplicar
        ss["reg_datos"] = {
            "tipo_entidad": tipo, "full_name": nombre.strip(), "email": email.strip().lower(),
            "password": password, "password2": password2, "nombre_entidad": nombre_entidad.strip(),
            "tarifa": tarifa, "giro": giro,
        }
        _ir_a(2)
        st.rerun()


# ---------------------------------------------------------------------------
# Paso 2
# ---------------------------------------------------------------------------
def _alternar(aparato: dict) -> None:
    clave = str(aparato["id"])
    if st.session_state.get(f"reg_chk_{clave}"):
        st.session_state["reg_sel"].setdefault(clave, {"cantidad": 1, "potencia_w": None, "horas": None})
    else:
        st.session_state["reg_sel"].pop(clave, None)


def _paso_2(ss) -> None:
    tipo = ss["reg_datos"]["tipo_entidad"]
    catalogo = get_catalogo_aparatos(tipo)
    nombre_tipo = ENTIDADES[tipo][0].lower()
    render_section_header(
        "¿Qué aparatos tienes?",
        "bolt",
        f"Marca los que hay en tu {nombre_tipo}. Este paso es opcional: puedes completarlo después en Mis aparatos.",
    )
    if catalogo is None:
        st.warning("No pudimos cargar la lista de aparatos. Puedes continuar y agregarlos después.")
        catalogo = []

    busqueda = st.text_input("Buscar aparato", placeholder="Escribe por ejemplo: nevera, aire, bombillo, bomba…", key="reg_busqueda")
    filtrados = [a for a in catalogo if coincide(a, busqueda)]
    seleccion = ss["reg_sel"]
    st.caption(f"{len(seleccion)} seleccionados · mostrando {len(filtrados)} de {len(catalogo)} aparatos")

    with st.container(height=430, border=True):
        if not filtrados:
            st.info("Ningún aparato coincide con la búsqueda. Puedes agregarlo como aparato propio más abajo.")
        orden = {t: i for i, t in enumerate(TIPOS_APARATO)}
        filtrados.sort(key=lambda a: (orden.get(a["tipo_aparato"], 99), a["id"]))  # orden del catálogo: de menor a mayor
        for tipo_ap, grupo in groupby(filtrados, key=lambda a: a["tipo_aparato"]):
            st.markdown(f"**{TIPOS_APARATO.get(tipo_ap, tipo_ap.title())}**")
            for a in grupo:
                clave = str(a["id"])
                st.checkbox(
                    f"{a['nombre']} — {a.get('descripcion') or ''}",
                    value=clave in seleccion,
                    key=f"reg_chk_{clave}",
                    on_change=_alternar,
                    args=(a,),
                    help=f"Uso típico: {a['potencia_w']:.0f} W durante {a['horas_uso_dia']:g} h/día ≈ {a['consumo_kwh_mes']:.0f} kWh/mes",
                )

    if seleccion:
        por_id = {str(a["id"]): a for a in catalogo}
        nombres = [por_id[k]["nombre"] for k in seleccion if k in por_id]
        st.markdown("**Seleccionados:** " + ", ".join(nombres))

    with st.expander("¿No encuentras un aparato? Agrégalo tú"):
        with st.form("reg_form_propio", clear_on_submit=True):
            p1, p2, p3, p4 = st.columns([2, 1, 1, 1])
            nombre_p = p1.text_input("Nombre", placeholder="Ej: acuario, horno de barro eléctrico")
            potencia_p = p2.number_input("Potencia (W)", min_value=1.0, max_value=200000.0, value=None, placeholder="Ej: 300")
            horas_p = p3.number_input("Horas al día", min_value=0.0, max_value=24.0, value=None, step=0.5, placeholder="Ej: 2")
            cantidad_p = p4.number_input("Cantidad", min_value=1, max_value=500, value=1, step=1)
            st.caption("Para un aparato que no está en la lista necesitamos su potencia (en la etiqueta) y cuántas horas lo usas.")
            if st.form_submit_button("Agregar aparato"):
                if len((nombre_p or "").strip()) < 2 or potencia_p is None or horas_p is None:
                    st.error("Completa nombre, potencia y horas de uso.")
                else:
                    ss["reg_propios"].append({"nombre": nombre_p.strip(), "potencia_w": potencia_p, "horas": horas_p, "cantidad": int(cantidad_p)})
                    st.success(f"Agregado: {nombre_p.strip()}")
    if ss["reg_propios"]:
        st.markdown("**Aparatos propios:** " + ", ".join(p["nombre"] for p in ss["reg_propios"]))

    b1, b2 = st.columns(2)
    b1.button("← Atrás", use_container_width=True, on_click=_ir_a, args=(1,), key="reg_btn_2_atras")
    total = len(seleccion) + len(ss["reg_propios"])
    texto = "Siguiente: cantidades y consumo →" if total else "Continuar sin aparatos →"
    b2.button(texto, type="primary", use_container_width=True, on_click=_ir_a, args=(3,), key="reg_btn_2_sig")


# ---------------------------------------------------------------------------
# Paso 3
# ---------------------------------------------------------------------------
def _quitar(clave: str) -> None:
    st.session_state["reg_sel"].pop(clave, None)
    st.session_state.pop(f"reg_chk_{clave}", None)


def _quitar_propio(indice: int) -> None:
    propios = st.session_state["reg_propios"]
    if 0 <= indice < len(propios):
        propios.pop(indice)


def _paso_3(ss) -> None:
    datos = ss["reg_datos"]
    catalogo = {str(a["id"]): a for a in (get_catalogo_aparatos(datos["tipo_entidad"]) or [])}
    seleccion = {k: v for k, v in ss["reg_sel"].items() if k in catalogo}
    render_section_header(
        "Cantidades y consumo",
        "chart",
        "La potencia y las horas son opcionales: si no las sabes, déjalas vacías y usamos un valor típico.",
    )
    st.caption("La potencia se mide en vatios (W) y viene en la etiqueta o el manual del aparato. El consumo mensual (kWh) lo calculamos con potencia × horas de uso.")

    total_kwh = 0.0
    if not seleccion and not ss["reg_propios"]:
        st.info("No elegiste aparatos. Puedes crear la cuenta así y agregarlos después en Mis aparatos.")

    for clave, item in seleccion.items():
        a = catalogo[clave]
        with st.container(border=True):
            cab, quitar = st.columns([5, 1])
            cab.markdown(f"**{a['nombre']}**  \nTípico: {a['potencia_w']:.0f} W × {a['horas_uso_dia']:g} h/día ≈ {a['consumo_kwh_mes']:.0f} kWh/mes")
            quitar.button("Quitar", key=f"reg_quitar_{clave}", on_click=_quitar, args=(clave,), use_container_width=True)
            c1, c2, c3 = st.columns(3)
            item["cantidad"] = int(c1.number_input("Cantidad", min_value=1, max_value=500, step=1, value=int(item.get("cantidad") or 1), key=f"reg_cant_{clave}"))
            item["potencia_w"] = c2.number_input("Potencia (W) · opcional", min_value=1.0, max_value=200000.0, value=item.get("potencia_w"), placeholder=f"{a['potencia_w']:.0f} (típico)", key=f"reg_pot_{clave}")
            item["horas"] = c3.number_input("Horas al día · opcional", min_value=0.0, max_value=24.0, step=0.5, value=item.get("horas"), placeholder=f"{a['horas_uso_dia']:g} (típico)", key=f"reg_horas_{clave}")
            kwh = _kwh_mes(item["potencia_w"] or a["potencia_w"], item["horas"] if item["horas"] is not None else a["horas_uso_dia"], item["cantidad"])
            total_kwh += kwh
            st.caption(f"≈ {kwh:.1f} kWh/mes")

    for i, p in enumerate(ss["reg_propios"]):
        with st.container(border=True):
            cab, quitar = st.columns([5, 1])
            cab.markdown(f"**{p['nombre']}** (aparato propio)  \n{p['potencia_w']:.0f} W × {p['horas']:g} h/día")
            quitar.button("Quitar", key=f"reg_quitar_p_{i}", on_click=_quitar_propio, args=(i,), use_container_width=True)
            kwh = _kwh_mes(p["potencia_w"], p["horas"], p["cantidad"])
            total_kwh += kwh
            st.caption(f"Cantidad {p['cantidad']} · ≈ {kwh:.1f} kWh/mes")

    if seleccion or ss["reg_propios"]:
        m1, m2 = st.columns(2)
        m1.metric("Consumo estimado de estos aparatos", f"{total_kwh:,.0f} kWh/mes")
        m2.metric("Costo estimado", f"${total_kwh * datos['tarifa']:,.0f} /mes", help=f"Con tu tarifa de ${datos['tarifa']:,.0f}/kWh")

    b1, b2 = st.columns(2)
    b1.button("← Atrás", use_container_width=True, on_click=_ir_a, args=(2,), key="reg_btn_3_atras")
    if b2.button("Crear cuenta", type="primary", use_container_width=True, key="reg_btn_crear"):
        aparatos = [
            {k: v for k, v in {
                "catalogo_id": int(clave),
                "cantidad": item["cantidad"],
                "potencia_w": item.get("potencia_w"),
                "horas_uso_dia": item.get("horas"),
            }.items() if v is not None}
            for clave, item in seleccion.items()
        ] + [
            {"nombre": p["nombre"], "potencia_w": p["potencia_w"], "horas_uso_dia": p["horas"], "cantidad": p["cantidad"]}
            for p in ss["reg_propios"]
        ]
        tipo = datos["tipo_entidad"]
        ok = register(
            email=datos["email"],
            password=datos["password"],
            full_name=datos["full_name"],
            role="empresa",
            escenario_usuario="real",
            nombre_empresa=datos["nombre_entidad"],
            tipo_empresa=datos.get("giro") or tipo,
            tarifa_kwh=datos["tarifa"],
            tipo_entidad=tipo,
            aparatos=aparatos,
        )
        if ok:
            # El administrador sigue en su sesión: solo confirmamos y dejamos el formulario limpio
            nombre, email, n = datos["full_name"], datos["email"], len(aparatos)
            _limpiar_estado()
            st.session_state["registro_ok"] = (
                f"Cuenta creada para {nombre} ({email}) con {n} aparato(s). Ya puede iniciar sesión."
            )
            st.rerun()
        else:
            st.caption("Si el correo ya está registrado, vuelve al paso 1 para cambiarlo.")


def render_registro() -> None:
    aviso = st.session_state.pop("registro_ok", None)
    if aviso:
        st.success(aviso)
    ss = _estado()
    paso = ss["reg_paso"]
    _indicador_pasos(paso)
    if paso == 1:
        _paso_1(ss)
    elif paso == 2:
        _paso_2(ss)
    else:
        _paso_3(ss)
