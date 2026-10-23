"""
Registro de usuarios nuevos (solo administrador, desde Administración), en tres pasos:
1. Tipo de entidad (hogar, negocio, empresa, institución, finca, comunidad), datos de la cuenta y tarifa.
   "Tengo paneles solares" abre la pantalla de la instalación (paneles, batería, inversor y consumo);
   al guardarla se vuelve a este paso.
2. Aparatos de esa categoría: buscador y lista por categorías (mismo diseño de "Agregar aparatos"
   en Mis aparatos), más aparatos propios que no estén en la lista.
3. Cantidad, potencia (W) y horas de uso opcionales por aparato, y creación de la cuenta.

El estado vive en st.session_state con prefijo "reg_" para poder ir y volver entre pasos.
Cada paso va en una tarjeta (st.container con borde); el estilo está en design.py ("Registro").
"""
from __future__ import annotations

import re
from html import escape

import streamlit as st

from api_client import get_catalogo_aparatos, register
from design import PALETTE, icon_svg, render_html_block
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
PASO_INSTALACION = 4  # pantalla de "Tengo paneles solares" (parte del paso 1)

# Instalación solar. La Guajira está a ~11° de latitud norte: los paneles van hacia el sur con una
# inclinación cercana a la latitud (10° a 15°; menos de 10° no deja que la lluvia los limpie).
ORIENTACIONES = {
    "sur": ("↓", "Sur (180° Ópt.)", 180.0),
    "sureste": ("↘", "Sureste (135°)", 135.0),
    "suroeste": ("↙", "Suroeste (225°)", 225.0),
    "este_oeste": ("⇄", "Este/Oeste (Bi)", None),
    "personalizada": ("◎", "Personalizada", None),
}
INCLINACION_OPTIMA = (10, 15)
TIPOS_PANEL = {  # código: (opción, nombre corto)
    "mono_perc": ("Monocristalino PERC / TOPCon (alta eficiencia ~22%)", "Monocristalino PERC / TOPCon"),
    "mono": ("Monocristalino estándar (~20%)", "Monocristalino"),
    "poli": ("Policristalino (~17%)", "Policristalino"),
    "bifacial": ("Bifacial (~22% más el reflejo de atrás)", "Bifacial"),
    "pelicula": ("Película delgada (~12%)", "Película delgada"),
}
QUIMICAS = {  # código: (opción, nombre corto)
    "lifepo4": ("Litio LiFePO₄ (ferrofosfato de litio: ciclo profundo y seguridad térmica)", "Litio LiFePO4"),
    "nmc": ("Litio NMC (alta densidad de energía)", "Litio NMC"),
    "agm": ("Plomo-ácido AGM / Gel (ciclo profundo)", "Plomo-ácido AGM/Gel"),
    "plomo": ("Plomo-ácido abierta (inundada)", "Plomo-ácido abierta"),
}
VOLTAJES = {"12": "12V", "24": "24V", "48": "48V", "alto": "Alto V"}
CONSUMO_DE = {
    "hogar": "del hogar", "negocio": "del negocio", "empresa": "de la empresa",
    "institucion": "de la institución", "finca": "de la finca", "comunidad": "de la comunidad",
}
INSTALACION_DEFECTO = {
    "potencia_panel_w": 500.0, "cantidad_paneles": 12, "orientacion": "sur", "azimut_grados": 180.0,
    "inclinacion_grados": 12, "tipo_panel": "mono_perc",
    "tiene_bateria": True, "quimica_bateria": "lifepo4", "voltaje": "48", "voltaje_banco_v": 48.0,
    "capacidad_ah": 200.0, "soc_pct": 78, "dod_pct": 90.0, "eficiencia_ciclo_pct": 95.0,
    "potencia_descarga_w": 5000.0,
    "potencia_inversor_w": 5000.0, "eficiencia_inversor_pct": 97.5, "rendimiento_pr_pct": 82.0,
    "potencia_pv_max_w": 6500.0,
    "consumo_diario_kwh": 14.5, "demanda_diurna_kwh": 6.5, "demanda_nocturna_kwh": 8.0, "carga_base_w": 200.0,
}
ETIQUETA_DIURNA = "Demanda solar diurna (06:00 - 18:00)"
ETIQUETA_NOCTURNA = "Demanda nocturna (18:00 - 06:00)"
ETIQUETA_BASE = "Carga base continua (nevera, router, equipos en espera)"


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------
def _estado() -> dict:
    ss = st.session_state
    ss.setdefault("reg_paso", 1)
    ss.setdefault("reg_datos", {"tipo_entidad": "hogar", "tarifa": 943.0})
    ss.setdefault("reg_sel", {})  # str(catalogo_id) -> {"cantidad", "potencia_w", "horas"}
    ss.setdefault("reg_propios", [])  # [{"nombre", "potencia_w", "horas", "cantidad"}]
    ss.setdefault("reg_inst", None)  # instalación solar guardada (pantalla "Tengo paneles solares")
    return ss


def _ir_a(paso: int) -> None:
    st.session_state["reg_paso"] = paso


def _limpiar_estado() -> None:
    for k in [k for k in st.session_state.keys() if str(k).startswith("reg_")]:
        del st.session_state[k]


def _kwh_mes(potencia_w: float, horas: float, cantidad: int = 1) -> float:
    return (potencia_w or 0) * (horas or 0) * (cantidad or 1) * 30 / 1000


# ---------------------------------------------------------------------------
# Piezas visuales
# ---------------------------------------------------------------------------
def _progreso(paso: int) -> None:
    """Barra delgada sobre la tarjeta con el avance del registro."""
    render_html_block(
        f'<div class="ag-reg-progreso" role="progressbar" aria-label="Paso {paso} de {len(PASOS)}: {PASOS[paso]}" '
        f'aria-valuenow="{paso}" aria-valuemin="1" aria-valuemax="{len(PASOS)}">'
        f'<span style="width: {paso / len(PASOS) * 100:.0f}%;"></span></div>'
    )


def _cabecera(titulo: str, subtitulo: str, icono: str, clase: str = "") -> None:
    render_html_block(
        f"""
        <div class="ag-reg-head {clase}">
            <span class="ag-reg-head__icono">{icon_svg(icono, 18, PALETTE["success"])}</span>
            <div>
                <div class="ag-reg-head__titulo">{escape(titulo)}</div>
                <div class="ag-reg-head__sub">{escape(subtitulo)}</div>
            </div>
        </div>
        """
    )


def _separador() -> None:
    render_html_block('<div class="ag-reg-separador"></div>')


# ---------------------------------------------------------------------------
# Paso 1
# ---------------------------------------------------------------------------
def _abrir_instalacion() -> None:
    """Guarda lo escrito en el paso 1 (sin validar todavía) y abre la pantalla de la instalación."""
    ss = st.session_state
    ss["reg_datos"].update({
        clave: ss[f"reg_{campo}"]
        for clave, campo in (
            ("tipo_entidad", "tipo_entidad"), ("full_name", "full_name"), ("email", "email"),
            ("password", "password"), ("password2", "password2"), ("nombre_entidad", "nombre_entidad"),
            ("tarifa", "tarifa"), ("giro", "giro"),
        )
        if f"reg_{campo}" in ss
    })
    _ir_a(PASO_INSTALACION)


def _potencia_pico_kw(inst: dict) -> float:
    return inst["potencia_panel_w"] * inst["cantidad_paneles"] / 1000


def _bateria_kwh(inst: dict) -> float:
    return inst["voltaje_banco_v"] * inst["capacidad_ah"] / 1000 if inst.get("tiene_bateria") else 0.0


def _resumen_instalacion(inst: dict) -> str:
    bateria = f"batería de {_bateria_kwh(inst):.2f} kWh" if inst.get("tiene_bateria") else "sin batería"
    return (
        f"{_potencia_pico_kw(inst):.2f} kWp ({inst['cantidad_paneles']} paneles de "
        f"{inst['potencia_panel_w']:,.0f} W) · {bateria}"
    )


def _paso_1(ss) -> None:
    datos = ss["reg_datos"]
    with st.container(border=True):
        _cabecera(
            "¿Qué vas a registrar?",
            "Con esto te mostramos solo los aparatos que aplican a tu caso.",
            "building",
            "ag-reg-head--cuenta",
        )
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

        _separador()
        _cabecera("Tus datos", "Ingresa tus credenciales y configuración tarifaria.", "person")
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre completo", value=datos.get("full_name", ""), placeholder="Juan Pérez", key="reg_full_name")
        email = c2.text_input("Correo electrónico", value=datos.get("email", ""), placeholder="juan.perez@correo.com", key="reg_email")
        c3, c4 = st.columns(2)
        password = c3.text_input(
            "Contraseña", type="password", value=datos.get("password", ""),
            placeholder="••••••••••••", help="Mínimo 6 caracteres", key="reg_password",
        )
        password2 = c4.text_input(
            "Repite la contraseña", type="password", value=datos.get("password2", ""),
            placeholder="••••••••••••", key="reg_password2",
        )

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

        inst = ss.get("reg_inst")
        if inst:
            render_html_block(
                f'<div class="ag-reg-paneles">{icon_svg("sun", 16, PALETTE["accent"])}'
                f"<span><b>Instalación solar registrada:</b> {escape(_resumen_instalacion(inst))}. "
                "Con estos datos calculamos la producción y el ahorro reales en lugar de simularlos.</span></div>"
            )

        b1, b2 = st.columns(2)
        b1.button(
            "Editar paneles solares →" if inst else "Tengo paneles solares →",
            use_container_width=True, on_click=_abrir_instalacion, key="reg_btn_paneles",
        )
        if b2.button("Siguiente: elegir aparatos →", type="primary", use_container_width=True, key="reg_btn_1"):
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
    with st.container(border=True):
        _cabecera(
            "¿Qué aparatos tienes?",
            f"Marca los que hay en tu {nombre_tipo}. Este paso es opcional: puedes completarlo después en Mis aparatos.",
            "bolt",
        )
        if catalogo is None:
            st.warning("No pudimos cargar la lista de aparatos. Puedes continuar y agregarlos después.")
            catalogo = []

        busqueda = st.text_input("Buscar aparato", placeholder="Escribe por ejemplo: nevera, aire, bombillo, bomba…", key="reg_busqueda")
        filtrados = [a for a in catalogo if coincide(a, busqueda)]
        seleccion = ss["reg_sel"]
        render_html_block(
            f'<div class="ag-add-caption">{len(seleccion)} seleccionados · mostrando {len(filtrados)} de {len(catalogo)} aparatos</div>'
        )

        # Lista predeterminada: una sección desplegable por categoría (mismo diseño de Mis aparatos)
        with st.container(height=430, border=False):
            if not filtrados:
                st.info("Ningún aparato coincide con la búsqueda. Puedes agregarlo como aparato propio más abajo.")
            orden = {t: n for n, t in enumerate(TIPOS_APARATO)}
            categorias = sorted({a["tipo_aparato"] for a in filtrados}, key=lambda t: orden.get(t, 99))
            for tipo_ap in categorias:
                del_tipo = sorted((a for a in filtrados if a["tipo_aparato"] == tipo_ap), key=lambda a: a["id"])
                marcados = sum(1 for a in del_tipo if str(a["id"]) in seleccion)
                etiqueta = f"**{TIPOS_APARATO.get(tipo_ap, tipo_ap.title())}** :gray-background[{len(del_tipo)} disponibles]"
                with st.expander(etiqueta, expanded=bool(busqueda) or marcados > 0):
                    render_html_block(f'<span class="ag-cat ag-cat--{tipo_ap}"></span>')
                    for a in del_tipo:
                        clave = str(a["id"])
                        st.checkbox(
                            f"{a['nombre']} :gray[{a.get('descripcion') or ''}]",
                            value=clave in seleccion,
                            key=f"reg_chk_{clave}",
                            on_change=_alternar,
                            args=(a,),
                            help=f"Uso típico: {a['potencia_w']:.0f} W durante {a['horas_uso_dia']:g} h/día ≈ {a['consumo_kwh_mes']:.0f} kWh/mes",
                        )

        if seleccion:
            por_id = {str(a["id"]): a for a in catalogo}
            nombres = [por_id[k]["nombre"] for k in seleccion if k in por_id]
            render_html_block(
                f'<div class="ag-reg-elegidos"><b>Seleccionados:</b> {escape(", ".join(nombres))}</div>'
            )

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
            render_html_block(
                '<div class="ag-reg-elegidos"><b>Aparatos propios:</b> '
                f'{escape(", ".join(p["nombre"] for p in ss["reg_propios"]))}</div>'
            )

        _separador()
        b1, b2 = st.columns([1, 2.6])
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


def _cabecera_aparato(nombre: str, detalle: str) -> str:
    return (
        f'<div class="ag-reg-aparato"><div class="ag-reg-aparato__nombre">{escape(nombre)}</div>'
        f'<div class="ag-reg-aparato__tipico">{escape(detalle)}</div></div>'
    )


def _paso_3(ss) -> None:
    datos = ss["reg_datos"]
    catalogo = {str(a["id"]): a for a in (get_catalogo_aparatos(datos["tipo_entidad"]) or [])}
    seleccion = {k: v for k, v in ss["reg_sel"].items() if k in catalogo}
    with st.container(border=True):
        _cabecera(
            "Cantidades y consumo",
            "La potencia y las horas son opcionales: si no las sabes, déjalas vacías y usamos un valor típico.",
            "money",
        )
        render_html_block(
            '<div class="ag-reg-nota">La potencia se mide en vatios (W) y viene en la etiqueta o el manual del '
            "aparato. El consumo mensual (kWh) lo calculamos con potencia × horas de uso.</div>"
        )

        total_kwh = 0.0
        if not seleccion and not ss["reg_propios"]:
            st.info("No elegiste aparatos. Puedes crear la cuenta así y agregarlos después en Mis aparatos.")

        for clave, item in seleccion.items():
            a = catalogo[clave]
            with st.container(border=True):
                cab, quitar = st.columns([3, 1], vertical_alignment="center")
                with cab:
                    render_html_block(_cabecera_aparato(
                        a["nombre"],
                        f"Típico: {a['potencia_w']:.0f} W × {a['horas_uso_dia']:g} h/día ≈ {a['consumo_kwh_mes']:.0f} kWh/mes",
                    ))
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
                cab, quitar = st.columns([3, 1], vertical_alignment="center")
                with cab:
                    render_html_block(_cabecera_aparato(
                        f"{p['nombre']} (aparato propio)", f"{p['potencia_w']:.0f} W × {p['horas']:g} h/día",
                    ))
                quitar.button("Quitar", key=f"reg_quitar_p_{i}", on_click=_quitar_propio, args=(i,), use_container_width=True)
                kwh = _kwh_mes(p["potencia_w"], p["horas"], p["cantidad"])
                total_kwh += kwh
                st.caption(f"Cantidad {p['cantidad']} · ≈ {kwh:.1f} kWh/mes")

        if seleccion or ss["reg_propios"]:
            render_html_block(
                f"""
                <div class="ag-reg-total">
                    <div>
                        <div class="ag-reg-total__label">Consumo estimado de estos aparatos</div>
                        <div class="ag-reg-total__valor">{total_kwh:,.0f} kWh/mes</div>
                    </div>
                    <div class="ag-reg-total__costo">
                        <div class="ag-reg-total__label">Costo estimado
                            <span class="ag-reg-total__info" title="Con tu tarifa de ${datos['tarifa']:,.0f}/kWh">
                                {icon_svg("info", 14, PALETTE["muted"])}
                            </span>
                        </div>
                        <div class="ag-reg-total__valor">${total_kwh * datos['tarifa']:,.0f} <span>/mes</span></div>
                    </div>
                </div>
                """
            )

        _separador()
        b1, b2 = st.columns([1, 2.6])
        b1.button("← Atrás", use_container_width=True, on_click=_ir_a, args=(2,), key="reg_btn_3_atras")
        if b2.button("Crear mi cuenta", type="primary", use_container_width=True, key="reg_btn_crear"):
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
                instalacion=_payload_instalacion(ss.get("reg_inst")),
            )
            if ok:
                # El administrador sigue en su sesión: solo confirmamos y dejamos el formulario limpio
                nombre, email, n = datos["full_name"], datos["email"], len(aparatos)
                inst = ss.get("reg_inst")
                solar = f" e instalación solar de {_potencia_pico_kw(inst):.2f} kWp" if inst else ""
                _limpiar_estado()
                st.session_state["registro_ok"] = (
                    f"Cuenta creada para {nombre} ({email}) con {n} aparato(s){solar}. Ya puede iniciar sesión."
                )
                st.rerun()
            else:
                st.caption("Si el correo ya está registrado, vuelve al paso 1 para cambiarlo.")


# ---------------------------------------------------------------------------
# Pantalla "Tengo paneles solares": paneles, batería, inversor y consumo
# ---------------------------------------------------------------------------
def _payload_instalacion(inst: dict | None) -> dict | None:
    """La instalación guardada en la sesión, con los nombres que espera la API."""
    if not inst:
        return None
    datos = {
        "potencia_panel_w": inst["potencia_panel_w"],
        "cantidad_paneles": int(inst["cantidad_paneles"]),
        "orientacion": inst["orientacion"],
        "azimut_grados": inst.get("azimut_grados"),
        "inclinacion_grados": inst.get("inclinacion_grados"),
        "tipo_panel": TIPOS_PANEL[inst["tipo_panel"]][1],
        "tiene_bateria": bool(inst.get("tiene_bateria")),
        "potencia_inversor_w": inst.get("potencia_inversor_w"),
        "eficiencia_inversor_pct": inst.get("eficiencia_inversor_pct"),
        "rendimiento_pr_pct": inst.get("rendimiento_pr_pct"),
        "potencia_pv_max_w": inst.get("potencia_pv_max_w"),
        "consumo_diario_kwh": inst.get("consumo_diario_kwh"),
        "demanda_diurna_kwh": inst.get("demanda_diurna_kwh"),
        "demanda_nocturna_kwh": inst.get("demanda_nocturna_kwh"),
        "carga_base_w": inst.get("carga_base_w"),
    }
    if inst.get("tiene_bateria"):
        datos.update({
            "quimica_bateria": QUIMICAS[inst["quimica_bateria"]][1],
            "voltaje_banco_v": inst["voltaje_banco_v"],
            "capacidad_ah": inst["capacidad_ah"],
            "soc_pct": inst.get("soc_pct"),
            "dod_pct": inst.get("dod_pct"),
            "eficiencia_ciclo_pct": inst.get("eficiencia_ciclo_pct"),
            "potencia_descarga_w": inst.get("potencia_descarga_w"),
        })
    return {k: v for k, v in datos.items() if v is not None}


def _cabecera_seccion(eyebrow: str, titulo: str, icono: str, *, pill: str = "", clase: str = "") -> None:
    pill_html = f'<span class="ag-reg-head__pill">{escape(pill)}</span>' if pill else ""
    render_html_block(
        f"""
        <div class="ag-reg-head ag-reg-head--inst {clase}">
            <span class="ag-reg-head__icono">{icon_svg(icono, 18, PALETTE["success"])}</span>
            <div class="ag-reg-head__texto">
                <div class="ag-reg-head__eyebrow">{escape(eyebrow)}</div>
                <div class="ag-reg-head__titulo">{escape(titulo)}</div>
            </div>
            {pill_html}
        </div>
        """
    )


def _etiqueta(texto: str, derecha_html: str = "") -> None:
    """Etiqueta de un campo con algo a la derecha (recomendación o valor actual)."""
    render_html_block(f'<div class="ag-inst-label"><span>{escape(texto)}</span>{derecha_html}</div>')


def _marcas(textos: list) -> None:
    """Rótulos bajo un deslizador: inicio, mitad y final."""
    partes = "".join(f"<span>{escape(t)}</span>" for t in textos)
    render_html_block(f'<div class="ag-inst-marcas">{partes}</div>')


def _calculo(tono: str, icono: str, titulo: str, valor: str, unidad: str, detalle: str) -> None:
    color = PALETTE["accent"] if tono == "solar" else PALETTE["info"]
    render_html_block(
        f"""
        <div class="ag-inst-calculo ag-inst-calculo--{tono}">
            <div class="ag-inst-calculo__dato">
                <span class="ag-inst-calculo__icono">{icon_svg(icono, 18, color)}</span>
                <div>
                    <div class="ag-inst-calculo__titulo">{escape(titulo)}</div>
                    <div class="ag-inst-calculo__valor">{escape(valor)} <span>{escape(unidad)}</span></div>
                </div>
            </div>
            <div class="ag-inst-calculo__detalle">{detalle}</div>
        </div>
        """
    )


def _estilos_unidades(unidades: dict, notas: dict) -> None:
    """Unidad dentro de cada campo numérico (W, %, kWh…) y nota a la derecha de su etiqueta."""
    reglas = []
    for etiqueta, unidad in unidades.items():
        campo = f'[data-testid="stNumberInput"]:has(input[aria-label="{etiqueta}"])'
        reglas.append(f'{campo} [data-testid="stNumberInputContainer"]::after {{ content: "{unidad}"; }}')
        reglas.append(
            f'{campo} [data-testid="stNumberInputStepDown"], {campo} [data-testid="stNumberInputStepUp"] {{ display: none; }}'
        )
    for etiqueta, nota in notas.items():
        campo = f'[data-testid="stNumberInput"]:has(input[aria-label="{etiqueta}"])'
        reglas.append(f'{campo} [data-testid="stWidgetLabel"]::after {{ content: "{nota}"; }}')
    st.markdown(f"<style>{' '.join(reglas)}</style>", unsafe_allow_html=True)


def _guardar_instalacion(inst: dict) -> None:
    st.session_state["reg_inst"] = inst
    st.session_state["reg_aviso"] = f"Instalación solar guardada: {_resumen_instalacion(inst)}."
    _ir_a(1)


def _quitar_instalacion() -> None:
    st.session_state["reg_inst"] = None
    st.session_state["reg_aviso"] = "Quitamos la instalación solar: el sistema se simulará con su consumo."
    _ir_a(1)


def _paso_instalacion(ss) -> None:
    datos = ss["reg_datos"]
    base = {**INSTALACION_DEFECTO, **(ss.get("reg_inst") or {})}

    # ---- 1. Paneles fotovoltaicos ----
    with st.container(border=True):
        tipo_actual = ss.get("reg_inst_tipo_panel", base["tipo_panel"])
        _cabecera_seccion("1 de 4 · Generación solar", "Paneles fotovoltaicos", "panel", pill=TIPOS_PANEL[tipo_actual][1])
        c1, c2 = st.columns(2)
        potencia_panel = c1.number_input(
            "Potencia nominal por panel", min_value=10.0, max_value=2000.0, step=10.0,
            value=float(base["potencia_panel_w"]), key="reg_inst_pot_panel", format="%.0f",
            help="Está en la etiqueta del panel como Pmax, medida en condiciones estándar (STC).",
        )
        cantidad = c2.number_input(
            "Cantidad de paneles instalados", min_value=1, max_value=10000, step=1,
            value=int(base["cantidad_paneles"]), key="reg_inst_cantidad",
        )
        wp = potencia_panel * cantidad
        _calculo(
            "solar", "sun", "Cálculo de potencia pico", f"{wp / 1000:.2f}", "kWp pico",
            f"{potencia_panel:,.0f} W × {cantidad} módulos = <b>{wp:,.0f} Wp</b>. La producción real cambia con la "
            "radiación, la inclinación, la temperatura y las sombras.",
        )

        _etiqueta(
            "Orientación azimutal de paneles",
            '<span class="ag-inst-recomendado">Recomendado en La Guajira: Sur (180°)</span>',
        )
        claves_or = list(ORIENTACIONES)
        orientacion = st.radio(
            "Orientación azimutal de paneles", claves_or,
            index=claves_or.index(base["orientacion"]) if base["orientacion"] in claves_or else 0,
            format_func=lambda k: ORIENTACIONES[k][0],
            captions=[ORIENTACIONES[k][1] for k in claves_or],
            horizontal=True, key="reg_inst_orientacion", label_visibility="collapsed",
        )
        azimut = ORIENTACIONES[orientacion][2]
        if orientacion == "personalizada":
            azimut = st.number_input(
                "Azimut personalizado", min_value=0.0, max_value=359.0, step=5.0,
                value=float(base.get("azimut_grados") or 180.0), key="reg_inst_azimut", format="%.0f",
                help="Hacia dónde miran los paneles: 0° norte, 90° este, 180° sur y 270° oeste.",
            )

        c3, c4 = st.columns(2)
        with c3:
            inclinacion_actual = int(ss.get("reg_inst_inclinacion", base["inclinacion_grados"]))
            optima = INCLINACION_OPTIMA[0] <= inclinacion_actual <= INCLINACION_OPTIMA[1]
            _etiqueta(
                "Ángulo de inclinación (°)",
                f'<span class="ag-inst-pill{" ag-inst-pill--ok" if optima else ""}">'
                f'{inclinacion_actual}°{" (Óptimo)" if optima else ""}</span>',
            )
            inclinacion = st.slider(
                "Ángulo de inclinación (°)", 0, 90, value=int(base["inclinacion_grados"]),
                key="reg_inst_inclinacion", label_visibility="collapsed",
            )
            _marcas(["0° (Plano)", "45°", "90° (Vertical)"])
        with c4:
            claves_tp = list(TIPOS_PANEL)
            tipo_panel = st.selectbox(
                "Tipo de panel fotovoltaico", claves_tp,
                index=claves_tp.index(base["tipo_panel"]) if base["tipo_panel"] in claves_tp else 0,
                format_func=lambda k: TIPOS_PANEL[k][0], key="reg_inst_tipo_panel",
            )

    # ---- 2. Batería ----
    voltaje_v = capacidad_ah = None
    quimica = voltaje = None
    soc = dod = eficiencia_ciclo = descarga = None
    with st.container(border=True):
        _cabecera_seccion("2 de 4 · Almacenamiento", "Batería de almacenamiento", "battery", clase="ag-reg-head--bateria")
        tiene_bateria = st.toggle("¿Tiene batería?", value=bool(base["tiene_bateria"]), key="reg_inst_tiene_bateria")
        if tiene_bateria:
            claves_q = list(QUIMICAS)
            quimica = st.selectbox(
                "Química y tecnología de la batería", claves_q,
                index=claves_q.index(base["quimica_bateria"]) if base["quimica_bateria"] in claves_q else 0,
                format_func=lambda k: QUIMICAS[k][0], key="reg_inst_quimica",
            )
            c1, c2 = st.columns(2)
            with c1:
                _etiqueta("Voltaje nominal del banco")
                claves_v = list(VOLTAJES)
                voltaje = st.radio(
                    "Voltaje nominal del banco", claves_v,
                    index=claves_v.index(base["voltaje"]) if base["voltaje"] in claves_v else 2,
                    format_func=VOLTAJES.get, horizontal=True, key="reg_inst_voltaje", label_visibility="collapsed",
                )
                if voltaje == "alto":
                    voltaje_v = st.number_input(
                        "Voltaje del banco", min_value=60.0, max_value=1500.0, step=10.0,
                        value=float(base["voltaje_banco_v"]) if base["voltaje"] == "alto" else 200.0,
                        key="reg_inst_voltaje_alto", format="%.0f",
                    )
                else:
                    voltaje_v = float(voltaje)
            with c2:
                capacidad_ah = st.number_input(
                    "Capacidad en amperios-hora", min_value=1.0, max_value=100000.0, step=10.0,
                    value=float(base["capacidad_ah"]), key="reg_inst_ah", format="%.0f",
                    help="La capacidad del banco completo, como la indica el fabricante (descarga en 10 horas, C10).",
                )
            wh = voltaje_v * capacidad_ah
            dod_actual = float(ss.get("reg_inst_dod", base["dod_pct"]))
            _calculo(
                "bateria", "battery", "Capacidad bruta almacenada", f"{wh / 1000:.2f}", "kWh nominales",
                f"{voltaje_v:,.0f} V × {capacidad_ah:,.0f} Ah = <b>{wh:,.0f} Wh</b>. Con una profundidad de descarga "
                f"(DoD) del {dod_actual:.0f}%, tienes <b>{wh / 1000 * dod_actual / 100:.2f} kWh</b> disponibles para la noche.",
            )
            c3, c4 = st.columns(2)
            with c3:
                soc_actual = int(ss.get("reg_inst_soc", base["soc_pct"]))
                _etiqueta(
                    "Estado de carga actual (SOC)",
                    f'<span class="ag-inst-pill ag-inst-pill--info">{soc_actual}% ({wh / 1000 * soc_actual / 100:.2f} kWh)</span>',
                )
                soc = st.slider(
                    "Estado de carga actual (SOC)", 0, 100, value=int(base["soc_pct"]),
                    key="reg_inst_soc", label_visibility="collapsed",
                )
                _marcas(["0% Vacía", "50% Mitad", "100% Llena"])
            with c4:
                dod = st.number_input(
                    "Profundidad de descarga máx. (DoD)", min_value=10.0, max_value=100.0, step=5.0,
                    value=float(base["dod_pct"]), key="reg_inst_dod", format="%.0f",
                    help="Hasta dónde se puede descargar sin acortar su vida útil: cerca de 90% en litio y 50% en plomo-ácido.",
                )
            c5, c6 = st.columns(2)
            eficiencia_ciclo = c5.number_input(
                "Eficiencia de ciclo (round-trip)", min_value=50.0, max_value=100.0, step=0.5,
                value=float(base["eficiencia_ciclo_pct"]), key="reg_inst_ef_ciclo", format="%.1f",
            )
            descarga = c6.number_input(
                "Potencia máx. de descarga (BMS)", min_value=100.0, max_value=1000000.0, step=100.0,
                value=float(base["potencia_descarga_w"]), key="reg_inst_descarga", format="%.0f",
            )
        else:
            render_html_block(
                '<div class="ag-reg-elegidos">Sin batería, la energía solar que no se use en el momento no se '
                "guarda para la noche.</div>"
            )

    # ---- 3. Inversor ----
    with st.container(border=True):
        inversor_actual = float(ss.get("reg_inst_inversor", base["potencia_inversor_w"]))
        _cabecera_seccion(
            "3 de 4 · Electrónica de potencia", "Inversor y rendimiento del sistema", "bolt",
            pill=f"{inversor_actual / 1000:.1f} kW CA",
        )
        c1, c2 = st.columns(2)
        inversor = c1.number_input(
            "Potencia nominal de salida CA", min_value=100.0, max_value=1000000.0, step=100.0,
            value=float(base["potencia_inversor_w"]), key="reg_inst_inversor", format="%.0f",
        )
        eficiencia_inv = c2.number_input(
            "Eficiencia máxima europea", min_value=80.0, max_value=100.0, step=0.1,
            value=float(base["eficiencia_inversor_pct"]), key="reg_inst_ef_inv", format="%.1f",
        )
        c3, c4 = st.columns(2)
        pr = c3.number_input(
            "Rendimiento global estimado (PR)", min_value=50.0, max_value=100.0, step=1.0,
            value=float(base["rendimiento_pr_pct"]), key="reg_inst_pr", format="%.0f",
            help="Lo que queda después de las pérdidas por temperatura, polvo, cableado e inversor. Si no lo sabes, deja 80%.",
        )
        pv_max = c4.number_input(
            "Potencia máxima CC admisible (PV Max)", min_value=100.0, max_value=1000000.0, step=100.0,
            value=float(base["potencia_pv_max_w"]), key="reg_inst_pv_max", format="%.0f",
        )
        if wp > pv_max:
            st.warning(
                f"Los paneles suman {wp:,.0f} Wp y el inversor admite hasta {pv_max:,.0f} W en corriente continua: "
                "revísalo con el instalador."
            )

    # ---- 4. Consumo ----
    with st.container(border=True):
        _cabecera_seccion(
            "4 de 4 · Perfil de demanda", f"Consumo de energía {CONSUMO_DE.get(datos.get('tipo_entidad'), 'del hogar')}",
            "home", clase="ag-reg-head--consumo",
        )
        with st.popover("¿Cómo leer tu factura?"):
            st.markdown(
                "En tu recibo de luz busca el **consumo del mes en kWh** (Air-E lo muestra junto a las lecturas del "
                "medidor). Divídelo entre los días facturados, normalmente 30, y tendrás el **consumo diario**.\n\n"
                "Si no sabes cómo se reparte entre el día y la noche, pon cerca de la mitad en cada uno."
            )
        c1, c2 = st.columns(2)
        diario = c1.number_input(
            "Consumo diario medio estimado", min_value=0.0, max_value=100000.0, step=0.5,
            value=float(base["consumo_diario_kwh"]), key="reg_inst_diario", format="%.1f",
        )
        c2.number_input(
            "Consumo mensual equivalente", min_value=0.0, value=round(diario * 30, 1), format="%.1f", disabled=True,
        )
        c3, c4 = st.columns(2)
        diurna = c3.number_input(
            ETIQUETA_DIURNA, min_value=0.0, max_value=100000.0, step=0.5,
            value=float(base["demanda_diurna_kwh"]), key="reg_inst_diurna", format="%.1f",
        )
        nocturna = c4.number_input(
            ETIQUETA_NOCTURNA, min_value=0.0, max_value=100000.0, step=0.5,
            value=float(base["demanda_nocturna_kwh"]), key="reg_inst_nocturna", format="%.1f",
        )
        carga_base = st.number_input(
            ETIQUETA_BASE, min_value=0.0, max_value=1000000.0, step=10.0,
            value=float(base["carga_base_w"]), key="reg_inst_carga_base", format="%.0f",
        )
        if diario > 0 and abs(diurna + nocturna - diario) > diario * 0.1:
            st.caption(
                f"La demanda del día y de la noche suman {diurna + nocturna:,.1f} kWh y el consumo diario es "
                f"{diario:,.1f} kWh: conviene que coincidan."
            )
        if diario > 0 and carga_base * 24 / 1000 > diario:
            st.caption(
                f"Una carga base de {carga_base:,.0f} W gasta {carga_base * 24 / 1000:,.1f} kWh al día, más que el "
                "consumo diario: revisa el valor."
            )

    # Unidades dentro de los campos y notas de las etiquetas
    _estilos_unidades(
        {
            "Potencia nominal por panel": "W",
            "Azimut personalizado": "°",
            "Voltaje del banco": "V",
            "Capacidad en amperios-hora": "Ah",
            "Profundidad de descarga máx. (DoD)": "% DoD",
            "Eficiencia de ciclo (round-trip)": "%",
            "Potencia máx. de descarga (BMS)": f"W ({(descarga or 0) / 1000:.1f} kW)",
            "Potencia nominal de salida CA": f"W ({inversor / 1000:.1f} kW)",
            "Eficiencia máxima europea": "%",
            "Rendimiento global estimado (PR)": "% PR",
            "Potencia máxima CC admisible (PV Max)": "W CC",
            "Consumo diario medio estimado": "kWh/día",
            "Consumo mensual equivalente": "kWh/mes",
            ETIQUETA_DIURNA: "kWh",
            ETIQUETA_NOCTURNA: "kWh",
            ETIQUETA_BASE: "W continuos",
        },
        {
            "Potencia nominal por panel": "STC 1000 W/m²",
            "Capacidad en amperios-hora": "C10",
            "Consumo diario medio estimado": "Consumo del mes ÷ 30",
            ETIQUETA_BASE: "Potencia media constante",
        },
    )

    # ---- Pie: referencia y botones ----
    with st.container(border=True):
        render_html_block('<span class="ag-inst-pie"></span>')
        hay_guardada = bool(ss.get("reg_inst"))
        columnas = st.columns([2.4, 1, 1, 1.3] if hay_guardada else [2.4, 1, 1.3], vertical_alignment="center")
        with columnas[0]:
            render_html_block(
                f'<div class="ag-inst-pie__nota">{icon_svg("shield", 18, PALETTE["success"])}'
                "<span>Datos de referencia del instalador y la ficha técnica. La instalación debe cumplir el "
                "RETIE (Reglamento Técnico de Instalaciones Eléctricas).</span></div>"
            )
        if hay_guardada:
            columnas[1].button("Quitar instalación", use_container_width=True, on_click=_quitar_instalacion, key="reg_inst_quitar")
        columnas[-2].button("Cancelar", use_container_width=True, on_click=_ir_a, args=(1,), key="reg_inst_cancelar")
        if columnas[-1].button(":material/save: Guardar instalación", type="primary", use_container_width=True, key="reg_inst_guardar"):
            if tiene_bateria and (not voltaje_v or not capacidad_ah):
                st.error("Indica el voltaje y la capacidad de la batería.")
                return
            _guardar_instalacion({
                "potencia_panel_w": potencia_panel, "cantidad_paneles": int(cantidad),
                "orientacion": orientacion, "azimut_grados": azimut, "inclinacion_grados": inclinacion,
                "tipo_panel": tipo_panel,
                "tiene_bateria": tiene_bateria, "quimica_bateria": quimica or base["quimica_bateria"],
                "voltaje": voltaje or base["voltaje"], "voltaje_banco_v": voltaje_v or base["voltaje_banco_v"],
                "capacidad_ah": capacidad_ah or base["capacidad_ah"], "soc_pct": soc if soc is not None else base["soc_pct"],
                "dod_pct": dod or base["dod_pct"], "eficiencia_ciclo_pct": eficiencia_ciclo or base["eficiencia_ciclo_pct"],
                "potencia_descarga_w": descarga or base["potencia_descarga_w"],
                "potencia_inversor_w": inversor, "eficiencia_inversor_pct": eficiencia_inv,
                "rendimiento_pr_pct": pr, "potencia_pv_max_w": pv_max,
                "consumo_diario_kwh": diario, "demanda_diurna_kwh": diurna,
                "demanda_nocturna_kwh": nocturna, "carga_base_w": carga_base,
            })
            st.rerun()


def render_registro() -> None:
    aviso = st.session_state.pop("registro_ok", None)
    if aviso:
        st.success(aviso)
    ss = _estado()
    paso = ss["reg_paso"]
    _progreso(1 if paso == PASO_INSTALACION else paso)
    aviso_paso = ss.pop("reg_aviso", None) if paso == 1 else None
    if aviso_paso:
        st.success(aviso_paso)
    if paso == PASO_INSTALACION:
        _paso_instalacion(ss)
    elif paso == 1:
        _paso_1(ss)
    elif paso == 2:
        _paso_2(ss)
    else:
        _paso_3(ss)
