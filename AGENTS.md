# AGENTS.md — Agente Solar Riohacha / Fonseca
Copiloto de energía limpia con IA para mitigar la asfixia tarifaria ($890 COP/kWh) y dar resiliencia ante apagones a hogares y PYMEs en La Guajira.

## Stack y estructura
- FastAPI (Python 3.11+), Streamlit (`streamlit_app/`), MySQL 8.0 / SQLite, Google GenAI SDK.
- `app/api/`: endpoints REST; `app/services/`: cálculo solar y Gemini; `docs/`: constitución y memoria.

## Comandos
- Iniciar API: `uvicorn app.main:app --reload --port 8000` | Frontend: `streamlit run streamlit_app/Home.py`
- Docker: `docker-compose up -d --build` | Tests: `pytest`

## Convenciones y Flujo Git
- Rama por tarea (`feature/*`, `fix/*`), commits atómicos y PR **solo bajo orden del usuario**.
- Reglas modulares: [.agents/rules/git-workflow.md](.agents/rules/git-workflow.md) y [.agents/rules/code-standards.md](.agents/rules/code-standards.md).

## Reglas de dominio / trampas conocidas
- Tarifa base $890 COP/kWh (Air-E). Siempre proveer fallback heurístico si no hay `GEMINI_API_KEY`.
- Diferenciar vista Residencial (simple) de Comercial (ROI técnico). Baterías: reserva mínima 30-40%.

## Forma de trabajar
- Planificar antes de tocar más de 2 archivos. Cambios incrementales y commits atómicos con Conventional Commits.

## Memoria
- Al empezar, lee [MEMORY.md](MEMORY.md). Al terminar, actualízalo con estado, decisiones y aprendizajes.
- Mantenerlo breve (<= 50 líneas). Nunca guardar claves, tokens ni datos personales.

## Límites
- ✅ Siempre: actualizar [MEMORY.md](MEMORY.md), crear rama por tarea y hacer commits atómicos.
- ⚠️ Pregunta antes: nuevas dependencias, cambios en esquemas de BD o apertura de PR.
- 🚫 Nunca: hacer commit directo a `main`/`develop`, ni alterar cálculos de ahorro con datos irreales.

## Verificación
- Validar sintaxis y tests locales (`pytest`), comprobar endpoints y verificar visualmente en Streamlit.
