# 🛡️ Seguridad y Gobernanza Técnica

Directrices para proteger la integridad del usuario, el hardware y el código.

## 1. Seguridad Operativa y Eléctrica
- Toda recomendación de manipulación física debe incluir advertencia
  de seguridad eléctrica y sugerir acompañamiento de un técnico certificado.
- Parámetros de baterías: proteger la profundidad de descarga (DoD) recomendada
  (mínimo 20% en litio, 50% en plomo-ácido) para evitar daños al banco.

## 2. Privacidad de Datos y Secretos
- Prohibido almacenar claves (`GEMINI_API_KEY`, passwords) en el repositorio.
- Los recibos de energía y datos de consumo no deben exponer PII no autorizada.
- Solo el administrador registra usuarios: la API rechaza registros sin sesión de administrador.

## 3. Gobernanza del Código y Soberanía del Usuario
- **Control Humano**: El usuario decide cuándo y hacia qué rama se crea un PR.
- El agente asiste, programa y commitea atómicamente, pero no toma decisiones
  de integración final de forma unilateral.
- Cero tolerancia a commits masivos "todo en uno" que oscurezcan el historial.

## 4. Auditoría Continua
- Todo cambio debe poder revertirse mediante git sin afectar la rama base.
- Preservar tests, linters y contratos de API existentes.
