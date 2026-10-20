"""
Agente de Recomendaciones.

Genera recomendaciones en lenguaje natural con Gemini, usando el inventario de aparatos
del usuario, la franja solar del pronóstico y el sistema solar sugerido. Si Gemini no está
disponible (sin clave, sin red o cuota agotada) usa reglas locales, también por aparato.
"""
import json
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.models import Empresa, Recomendacion
from app.services.contexto_energetico import (
    CONSEJOS_POR_TIPO,
    dimensionar_sistema,
    obtener_franja_solar,
    resumen_inventario,
    texto_inventario_para_prompt,
    _minuscula_inicial,
    nombre_aparato,
)
from app.services.gemini_client import obtener_respuesta_gemini

# Ahorro por reemplazos frecuentes: (código actual, código eficiente, texto)
REEMPLAZOS = [
    ("bombillo_incandescente", "bombillo_led", "Cambia {n} bombillo(s) incandescente(s) por LED de 9 W: dan la misma luz con 85% menos energía."),
    ("bombillo_ahorrador", "bombillo_led", "Cambia {n} bombillo(s) ahorrador(es) por LED de 9 W cuando se dañen: gastan cerca de la mitad."),
    ("nevera_antigua", "nevera", "Tu nevera antigua gasta bastante más que una nueva. Si la cambias, elige una con etiqueta de eficiencia A."),
]


class AgenteRecomendaciones:
    """Genera recomendaciones de ahorro energético."""

    SYSTEM_PROMPT = """Eres un experto en eficiencia energética y energía solar en La Guajira, Colombia.
Conoces que:
- La radiación solar de la región es alta todo el año.
- La tarifa residencial en Colombia es la misma a cualquier hora: mover consumo a las horas de sol solo ahorra dinero si el usuario tiene paneles solares.
- Hay cortes de energía frecuentes en la región.
- El polvo y la arena reducen la eficiencia de los paneles (~5-15%) si no se limpian.
Generas SIEMPRE recomendaciones en español, cortas (1-2 oraciones), prácticas, accionables y específicas,
nombrando los aparatos reales del usuario y con horarios cuando aplique. Cada recomendación lleva un impacto económico mensual estimado en COP."""

    async def contexto(self, db: Session, empresa: Empresa) -> Dict:
        resumen = resumen_inventario(db, empresa)
        return {
            "resumen": resumen,
            "franja": await obtener_franja_solar(),
            "dimensionamiento": dimensionar_sistema(db, empresa, resumen),
        }

    async def generar(
        self,
        db: Session,
        empresa: Empresa,
        analisis_solar: Dict,
        analisis_consumo: Dict,
    ) -> List[Recomendacion]:
        """Genera y guarda recomendaciones para una empresa."""
        ctx = await self.contexto(db, empresa)
        recomendaciones_texto = await self._generar_con_llm(empresa, analisis_solar, analisis_consumo, ctx)
        usado_llm = bool(recomendaciones_texto)
        if not recomendaciones_texto:
            recomendaciones_texto = self._generar_con_reglas(empresa, analisis_solar, analisis_consumo, ctx)

        creadas = []
        escenario = empresa.escenario_default or "demo"
        origen = "llm" if usado_llm else "reglas"
        confiabilidad_datos = 80.0 if escenario == "real" else 55.0
        for rec in recomendaciones_texto:
            r = Recomendacion(
                empresa_id=empresa.id,
                texto=rec["texto"],
                tipo=rec.get("tipo", "ahorro"),
                impacto_estimado_cop=rec.get("impacto_cop", 0),
                confianza_pct=rec.get("confianza", 75.0),
                escenario=escenario,
                origen_dato=origen,
                confiabilidad_datos=confiabilidad_datos,
            )
            db.add(r)
            creadas.append(r)
        db.commit()
        for r in creadas:
            db.refresh(r)
        return creadas

    async def _generar_con_llm(
        self,
        empresa: Empresa,
        solar: Dict,
        consumo: Dict,
        ctx: Optional[Dict] = None,
    ) -> List[Dict]:
        """Llama a Gemini. Devuelve [] si no hay clave, no responde o la respuesta no es JSON válido."""
        es_hogar = (getattr(empresa, "tipo_entidad", None) or empresa.tipo) == "hogar"
        desc_tipo = "Hogar / Familia Residencial" if es_hogar else f"{getattr(empresa, 'tipo_entidad', None) or 'empresa'} (giro: {empresa.tipo or 'PYME'})"
        ciudad = empresa.ciudad or "La Guajira"
        contexto_adicional = (
            "Como es un hogar, enfócate en hábitos familiares y electrodomésticos; evita términos industriales."
            if es_hogar else
            "Enfócate en eficiencia operativa, reducción de picos de potencia, equipos del negocio y retorno de inversión."
        )

        bloque_aparatos = ""
        if ctx:
            resumen, franja, dim = ctx["resumen"], ctx.get("franja"), ctx["dimensionamiento"]
            paneles = "SÍ tiene paneles solares" if resumen["tiene_paneles"] else "NO tiene paneles solares"
            franja_txt = f"Franja de mayor radiación: {franja['texto']} (≈{franja['ghi_dia_kwh_m2']} kWh/m² en el día)." if franja else "Sin pronóstico horario disponible."
            bloque_aparatos = f"""
Aparatos registrados por el usuario (consumo estimado mensual):
{texto_inventario_para_prompt(resumen)}

Situación: el usuario {paneles}. {franja_txt}
Sistema solar sugerido para su consumo: {dim['kwp_sugerido']} kWp (≈{dim['produccion_mes_kwh']:.0f} kWh/mes, ahorro ≈${dim['ahorro_mes_cop']:,.0f}/mes) y batería de {dim['bateria_kwh_sugerida']} kWh para cargas críticas.

Reglas:
- Al menos 3 recomendaciones deben nombrar aparatos concretos de la lista y su impacto.
- Si NO tiene paneles, no recomiendes mover consumo a las horas de sol para ahorrar: la tarifa no cambia por hora. Recomienda eficiencia, reemplazos o el sistema solar sugerido.
- Si SÍ tiene paneles, recomienda usar los aparatos que se pueden mover de horario dentro de la franja de mayor radiación.
- Si no registró aparatos, una recomendación debe invitarlo a registrarlos en "Mis aparatos"."""

        prompt = f"""Genera EXACTAMENTE 5 recomendaciones de ahorro energético para el cliente "{empresa.nombre}" (perfil: {desc_tipo}) en {ciudad}, La Guajira.
{contexto_adicional}

Datos solares (últimos 30 días):
- Radiación GHI promedio: {solar.get('promedio_ghi', 'N/A')} kWh/m²/día
- Capacidad de paneles instalados: {empresa.capacidad_paneles_kw} kW

Datos de consumo (últimos 30 días):
- Consumo total: {consumo.get('total_kwh', 0)} kWh · promedio diario: {consumo.get('promedio_diario_kwh', 0)} kWh
- Demanda pico: {consumo.get('demanda_pico_kw', 0)} kW · anomalías: {consumo.get('num_anomalias', 0)}
- Tarifa: {empresa.tarifa_kwh} COP/kWh
{bloque_aparatos}

Responde EXCLUSIVAMENTE con un JSON válido con este formato (sin texto adicional):
{{"recomendaciones": [
  {{"texto": "...", "tipo": "ahorro|redistribucion|contingencia|mantenimiento", "impacto_cop": 50000, "confianza": 85}}
]}}"""

        try:
            respuesta = await obtener_respuesta_gemini(prompt=prompt, system_instruction=self.SYSTEM_PROMPT)
        except Exception as e:  # sin clave configurada u otro error: se usan las reglas
            print(f"[RECOMENDACIONES] Gemini no disponible, se usan reglas: {e}")
            return []
        if not respuesta:
            return []
        try:
            start, end = respuesta.find("{"), respuesta.rfind("}")
            if start == -1 or end == -1:
                return []
            data = json.loads(respuesta[start:end + 1])
            recs = [r for r in data.get("recomendaciones", []) if isinstance(r, dict) and r.get("texto")]
            return recs[:5]
        except (json.JSONDecodeError, ValueError):
            return []

    # ------------------------------------------------------------------
    # Reglas locales (respaldo)
    # ------------------------------------------------------------------
    def _reglas_por_aparato(self, empresa: Empresa, ctx: Dict) -> List[Dict]:
        resumen, franja, dim = ctx["resumen"], ctx.get("franja"), ctx["dimensionamiento"]
        tarifa = float(empresa.tarifa_kwh or 943.0)
        recs: List[Dict] = []

        if not resumen["tiene_aparatos"]:
            return [{
                "texto": "Registra tus aparatos en \"Mis aparatos\": con tu lista te diremos cuánto gasta cada uno y cuándo conviene usarlos.",
                "tipo": "ahorro", "impacto_cop": 0, "confianza": 90.0,
            }]

        mayor = resumen["top"][0]
        if len(resumen["aparatos"]) == 1 and not resumen["no_identificado_kwh_mes"]:
            consejo = CONSEJOS_POR_TIPO.get(mayor["tipo_aparato"], CONSEJOS_POR_TIPO["otro"])
            recs.append({
                "texto": f"Tu {nombre_aparato(mayor)} gasta ≈{mayor['kwh_mes']:.0f} kWh al mes (≈${mayor['costo_mes']:,.0f}). {consejo}",
                "tipo": "ahorro", "impacto_cop": round(mayor["costo_mes"] * 0.15), "confianza": 75.0,
            })
            recs.append({
                "texto": "Registra el resto de tus aparatos en \"Mis aparatos\" para saber cuál pesa más en tu factura.",
                "tipo": "ahorro", "impacto_cop": 0, "confianza": 90.0,
            })
        elif mayor["porcentaje"] >= 20:
            consejo = CONSEJOS_POR_TIPO.get(mayor["tipo_aparato"], CONSEJOS_POR_TIPO["otro"])
            recs.append({
                "texto": f"Tu {nombre_aparato(mayor)} es el {mayor['porcentaje']:.0f}% de tu consumo (≈${mayor['costo_mes']:,.0f}/mes). {consejo}",
                "tipo": "ahorro", "impacto_cop": round(mayor["costo_mes"] * 0.15), "confianza": 80.0,
            })

        if resumen["tiene_paneles"] and franja and resumen["desplazables"]:
            nombres = " y ".join(_minuscula_inicial(a["nombre"]) for a in resumen["desplazables"][:2])
            # Sin artículos: "la secadora y horno" suena mal y cada aparato lleva uno distinto
            kwh = sum(a["kwh_mes"] for a in resumen["desplazables"])
            recs.append({
                "texto": f"Programa {franja['texto']} el uso de: {nombres}. Con el sol más fuerte, tus paneles cubren ese consumo en vez de la red.",
                "tipo": "redistribucion", "impacto_cop": round(kwh * 0.8 * tarifa), "confianza": 80.0,
            })

        por_codigo = {}
        for a in resumen["aparatos"]:
            if a["codigo"]:
                por_codigo.setdefault(a["codigo"], []).append(a)
        for actual, eficiente, texto in REEMPLAZOS:
            for a in por_codigo.get(actual, []):
                # Diferencia de consumo con el equivalente eficiente, con las mismas horas de uso
                w_eficiente = {"bombillo_led": 9.0, "nevera": 150.0}[eficiente]
                factor = 10.0 / 12.0 if actual == "nevera_antigua" else 1.0  # la nevera nueva cicla menos
                kwh_ahorro = max(0.0, (a["potencia_w"] - w_eficiente * factor) * a["horas_dia"] * a["cantidad"] * 30 / 1000)
                if kwh_ahorro > 1:
                    recs.append({
                        "texto": texto.format(n=a["cantidad"]) + f" Ahorro ≈{kwh_ahorro:.0f} kWh al mes.",
                        "tipo": "ahorro", "impacto_cop": round(kwh_ahorro * tarifa), "confianza": 85.0,
                    })

        for a in por_codigo.get("aire_ventana", []):
            recs.append({
                "texto": f"Tu {_minuscula_inicial(a['nombre'])} gasta ≈{a['kwh_mes']:.0f} kWh/mes. Un mini split inverter del mismo tamaño consume cerca de 40% menos.",
                "tipo": "ahorro", "impacto_cop": round(a["kwh_mes"] * 0.4 * tarifa), "confianza": 70.0,
            })
        for a in por_codigo.get("decodificador", []):
            kwh = a["potencia_w"] * 8 * a["cantidad"] * 30 / 1000
            recs.append({
                "texto": "Desconecta el decodificador en la noche o con una regleta: aunque no lo uses, sigue consumiendo.",
                "tipo": "ahorro", "impacto_cop": round(kwh * tarifa), "confianza": 75.0,
            })

        total = resumen["total_kwh_mes"] or 0
        if resumen["no_identificado_kwh_mes"] and total and resumen["no_identificado_kwh_mes"] / total >= 0.3:
            recs.append({
                "texto": f"Tu factura tiene ≈{resumen['no_identificado_kwh_mes']:.0f} kWh/mes que tus aparatos registrados no explican. Revisa si falta alguno en tu lista o si alguno se usa más horas de las indicadas.",
                "tipo": "mantenimiento", "impacto_cop": 0, "confianza": 70.0,
            })

        if (empresa.capacidad_paneles_kw or 0) == 0 and dim.get("consumo_mes_kwh"):
            recs.append({
                "texto": f"Un sistema solar de {dim['kwp_sugerido']} kWp produciría ≈{dim['produccion_mes_kwh']:.0f} kWh al mes, cerca del {dim['cobertura_pct']:.0f}% de tu consumo.",
                "tipo": "ahorro", "impacto_cop": dim["ahorro_mes_cop"], "confianza": 70.0,
            })
        return recs

    def _generar_con_reglas(
        self,
        empresa: Empresa,
        solar: Dict,
        consumo: Dict,
        ctx: Optional[Dict] = None,
    ) -> List[Dict]:
        """Recomendaciones basadas en reglas: primero las de los aparatos del usuario, luego las generales."""
        recomendaciones: List[Dict] = self._reglas_por_aparato(empresa, ctx) if ctx else []
        promedio_kwh = (consumo.get("promedio_diario_kwh") or 0.0) if consumo else 0.0
        promedio_ghi = (solar.get("promedio_ghi") or 0.0) if solar else 0.0
        tarifa = (empresa.tarifa_kwh or 943.0) if empresa else 943.0
        num_anomalias = (consumo.get("num_anomalias") or 0) if consumo else 0
        es_hogar = bool(empresa) and (getattr(empresa, "tipo_entidad", None) or empresa.tipo) == "hogar"
        ciudad = (empresa.ciudad or "La Guajira") if empresa else "La Guajira"
        tiene_paneles = bool(empresa and (empresa.capacidad_paneles_kw or 0) > 0)
        dim = (ctx or {}).get("dimensionamiento") or {}

        # Generales (solo se agregan hasta completar 5)
        ya_redistribuye = any(r.get("tipo") == "redistribucion" for r in recomendaciones)
        if promedio_ghi > 4.5 and tiene_paneles and not ya_redistribuye:
            texto = (
                f"Lave, planche o encienda los electrodomésticos de mayor consumo entre 10 AM y 2 PM, cuando sus paneles producen más en {ciudad}."
                if es_hogar else
                f"Concentre operaciones de alto consumo entre 10 AM y 2 PM, cuando sus paneles producen más en {ciudad}."
            )
            recomendaciones.append({"texto": texto, "tipo": "redistribucion", "impacto_cop": round(promedio_kwh * 0.2 * tarifa), "confianza": 85.0})

        if promedio_kwh > 0:
            texto = (
                "Apague luces y aires acondicionados que no se estén usando en la noche: es cuando más se acumula consumo en casa."
                if es_hogar else
                "Evite encender al mismo tiempo los equipos de mayor potencia entre 6 PM y 9 PM, la hora de mayor demanda de la red: así no sobrecarga su instalación."
            )
            recomendaciones.append({"texto": texto, "tipo": "redistribucion", "impacto_cop": round(promedio_kwh * 0.1 * tarifa), "confianza": 80.0})

        if empresa and (empresa.capacidad_paneles_kw or 0) == 0 and not dim.get("consumo_mes_kwh"):
            kwp = dim.get("kwp_sugerido") or (2.5 if es_hogar else 10.0)
            recomendaciones.append({
                "texto": f"Un sistema solar de {kwp} kWp podría cubrir buena parte de su consumo diurno y reducir cada factura de Air-E.",
                "tipo": "ahorro", "impacto_cop": round(promedio_kwh * 0.4 * tarifa * 30), "confianza": 75.0,
            })

        if num_anomalias > 0:
            recomendaciones.append({
                "texto": f"Se detectaron {num_anomalias} días con consumo inusualmente alto. Revise qué equipos estuvieron encendidos esos días.",
                "tipo": "mantenimiento", "impacto_cop": round(promedio_kwh * 0.15 * tarifa), "confianza": 70.0,
            })

        if empresa and (empresa.capacidad_bateria_kwh or 0) == 0:
            bateria = dim.get("bateria_kwh_sugerida") or (5.0 if es_hogar else 30.0)
            texto = (
                f"Una batería de {bateria} kWh mantendría encendidas la nevera, las luces y el internet durante los cortes de luz."
                if es_hogar else
                f"Una batería de {bateria} kWh respaldaría sus equipos críticos (refrigeración, iluminación, caja) durante los cortes."
            )
            recomendaciones.append({"texto": texto, "tipo": "contingencia", "impacto_cop": 50000 if es_hogar else 200000, "confianza": 70.0})

        return recomendaciones[:5]


agente_recomendaciones = AgenteRecomendaciones()
