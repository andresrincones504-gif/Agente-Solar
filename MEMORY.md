# MEMORY.md — Agente Solar Riohacha / Fonseca
Memoria del proyecto entre sesiones. Máximo ~50 líneas: resume o elimina lo que ya no aporte.

## Estado actual
- La app se presenta como **Ka'i**; ubicación por defecto Fonseca, La Guajira (configurable con `LOCATION_*`).
- Docker Compose: API en 8002, Streamlit en 8503 y MySQL en 3308 (en local: 8000 y 8501).
- Datos y modelos migrados a Fonseca y Riohacha (La Guajira), radiación pico ~5.85 kWh/m²/día.
- Motor dual activo: Google GenAI (`gemini-3.5-flash-lite`, en `GEMINI_MODEL`) + fallback heurístico local.
- Perfiles: Residencial cuando la entidad es hogar; negocio, empresa, institución, finca y comunidad ven la vista comercial.
- Entrada solo con login (con botón de cuenta demo); las cuentas nuevas las crea el administrador.
- Alertas: clima general del municipio (calor, lluvia, apagón, polvo, poca radiación); avisos por aparato en Mis aparatos.
- Rama de trabajo actual del frontend: `cambio_fronen2`. Rama base de desarrollo: `develop`.
- Tests: 58 pasan; 4 fallan en `tests/test_alertas_aparatos.py` (pruebas del esquema anterior de alertas).

## Decisiones (y por qué)
- **Motor dual IA + Heurística**: Asegurar operación continua offline durante cortes o sin API Key.
- **Flujo Git estricto por ramas**: Evitar tocar `develop`/`main` directo y esperar orden para PRs.
- **Desacoplamiento FastAPI/Streamlit**: Permite escalar API y frontend de forma independiente.
- **Regla <= 50 líneas**: Modularizar detalles en [docs/memory/decisions.md](docs/memory/decisions.md) y [docs/memory/system-patterns.md](docs/memory/system-patterns.md).
- **Autoría del Proyecto**: Asignada formalmente al equipo Code Masters y sus 4 integrantes en LICENSE y AUTHORS.md.
- **Tarifa de referencia $890 COP/kWh**: valor vigente para la documentación (antes $943).
- **Registro solo por administrador**: los demás roles solo inician sesión; la API lo exige.

## Aprendizajes y errores a evitar
- No hardcodear `GEMINI_API_KEY` ni asumir conexión permanente a internet en La Guajira.
- Tarifa real de Air-E es ~$890 COP/kWh; nunca inventar métricas de ahorro sin sustento.
- Proteger profundidad de descarga en baterías (DoD) para no acortar su vida útil.
- En Windows el repo usa CRLF: desde Linux/Docker usar `git -c core.autocrlf=true` para no ver todo modificado.

## Próximos pasos
- Afinar calibración del orquestador autónomo de baterías ante simulaciones de apagón.
- Robustecer suite de tests unitarios y de integración para endpoints clave.
- Pasar a $890 los valores por defecto que aún usan $943 (código, seed, datos demo y README).
- Reemplazar `tests/test_alertas_aparatos.py` por pruebas de las alertas del municipio.
- Agregar `.agents/rules/` (referenciado en AGENTS.md), que aún no está en este repositorio.
