# 🏛️ Registro de Decisiones de Arquitectura (ADR)

Histórico de decisiones clave tomadas en el proyecto.

## ADR-001: Motor Dual de Recomendaciones (IA + Heurística)
- **Decisión**: Integrar Gemini API con un motor heurístico de respaldo.
- **Razón**: Garantizar funcionamiento offline/sin credenciales durante demos o cortes.

## ADR-002: Arquitectura Desacoplada (FastAPI + Streamlit)
- **Decisión**: Backend REST independiente de la interfaz Streamlit.
- **Razón**: Permite evolucionar el frontend o integrar clientes móviles sin tocar lógica.

## ADR-003: Enfoque Regional (Riohacha y Fonseca, La Guajira)
- **Decisión**: Adaptar perfiles solares, tarifas ($890 COP/kWh; antes $943) y datos a La Guajira.
- **Razón**: Resolver la paradoja energética real de la región bajo criterios MinTIC.

## ADR-004: Adopción del SDK `google-genai` y Modelos Flash
- **Decisión**: Usar SDK oficial `google-genai`; modelo por defecto `gemini-3.5-flash-lite` (`GEMINI_MODEL`).
- **Razón**: Respuestas ultrarrápidas, menor latencia y costo eficiente.

## ADR-005: Flujo Git Estricto por Ramas Atómicas
- **Decisión**: Ramas `feature/*`, commits atómicos y PR condicionado a orden manual.
- **Razón**: Mantener estabilidad en `develop`/`main` y control total del desarrollador.

## ADR-006: Registro Restringido al Administrador
- **Decisión**: La entrada es solo login; el registro guiado vive en Administración.
- **Razón**: Solo el administrador da de alta usuarios; la API rechaza registros sin su sesión.

## ADR-007: Identidad Ka'i y Rediseño del Frontend
- **Decisión**: Nombre y logo Ka'i, menú lateral propio y paleta oscura (verde #2FA38A, dorado #D8A24A).
- **Razón**: Interfaz más clara y menos técnica para hogares y negocios.

## ADR-008: Alertas del Municipio
- **Decisión**: Alertas solo del clima general de la ubicación; los avisos por aparato van en Mis aparatos.
- **Razón**: Las alertas deben servir a cualquier usuario de la zona, tenga o no aparatos registrados.
