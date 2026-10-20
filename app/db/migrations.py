from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_schema_compatibility(engine: Engine) -> None:
    """Apply small, targeted schema fixes for older databases.

    The project currently uses ``create_all`` for fresh setups, but that does
    not evolve existing tables. This helper patches known schema drift without
    requiring users to drop their database volume.
    """
    inspector = inspect(engine)

    if inspector.has_table("users"):
        user_columns = {column["name"] for column in inspector.get_columns("users")}

        role_column = next(
            (column for column in inspector.get_columns("users") if column["name"] == "role"),
            None,
        )
        role_values = list(getattr(role_column["type"], "enums", []) if role_column else [])
        if role_values != ["admin", "empresa", "analista"]:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE users "
                        "MODIFY COLUMN role ENUM('admin', 'empresa', 'analista') "
                        "NOT NULL DEFAULT 'empresa'"
                    )
                )

        if "vista_preferida" not in user_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE users "
                        "ADD COLUMN vista_preferida ENUM('simple', 'detallado', 'operacional') "
                        "NOT NULL DEFAULT 'simple' AFTER `role`"
                    )
                )
        if "escenario_usuario" not in user_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE users "
                        "ADD COLUMN escenario_usuario VARCHAR(20) "
                        "NOT NULL DEFAULT 'real' AFTER `role`"
                    )
                )

    if inspector.has_table("radiacion_solar"):
        radiacion_columns = {column["name"] for column in inspector.get_columns("radiacion_solar")}
        missing_radiacion_columns = []

        if "temperatura_max" not in radiacion_columns:
            missing_radiacion_columns.append("ADD COLUMN temperatura_max FLOAT NULL")
        if "temperatura_min" not in radiacion_columns:
            missing_radiacion_columns.append("ADD COLUMN temperatura_min FLOAT NULL")
        if "precipitacion_mm" not in radiacion_columns:
            missing_radiacion_columns.append("ADD COLUMN precipitacion_mm FLOAT NULL")
        if "viento_kmh_max" not in radiacion_columns:
            missing_radiacion_columns.append("ADD COLUMN viento_kmh_max FLOAT NULL")
        if "escenario" not in radiacion_columns:
            missing_radiacion_columns.append("ADD COLUMN escenario VARCHAR(20) NOT NULL DEFAULT 'demo'")
        if "origen_dato" not in radiacion_columns:
            missing_radiacion_columns.append("ADD COLUMN origen_dato VARCHAR(40) NOT NULL DEFAULT 'seed_demo'")
        if "confiabilidad" not in radiacion_columns:
            missing_radiacion_columns.append("ADD COLUMN confiabilidad FLOAT NULL DEFAULT 50")

        if missing_radiacion_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE radiacion_solar "
                        + ", ".join(missing_radiacion_columns)
                    )
                )

    if inspector.has_table("empresas"):
        empresa_columns = {column["name"] for column in inspector.get_columns("empresas")}
        if "escenario_default" not in empresa_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE empresas "
                        "ADD COLUMN escenario_default VARCHAR(20) NOT NULL DEFAULT 'demo'"
                    )
                )
        if "tipo_entidad" not in empresa_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE empresas ADD COLUMN tipo_entidad VARCHAR(30) NULL"))
                connection.execute(text("CREATE INDEX ix_empresas_tipo_entidad ON empresas (tipo_entidad)"))
        # Empresas creadas antes de existir tipo_entidad: se deduce del campo 'tipo' del registro anterior
        # (hogar y comunidad tenian opcion propia; el resto venia de "Empresa / PYME").
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE empresas SET tipo_entidad = CASE "
                    "WHEN tipo = 'hogar' THEN 'hogar' "
                    "WHEN tipo = 'comunidad' THEN 'comunidad' "
                    "ELSE 'empresa' END "
                    "WHERE tipo_entidad IS NULL"
                )
            )

    if inspector.has_table("consumo_energetico"):
        consumo_columns = {column["name"] for column in inspector.get_columns("consumo_energetico")}
        missing_consumo_columns = []
        if "escenario" not in consumo_columns:
            missing_consumo_columns.append("ADD COLUMN escenario VARCHAR(20) NOT NULL DEFAULT 'demo'")
        if "origen_dato" not in consumo_columns:
            missing_consumo_columns.append("ADD COLUMN origen_dato VARCHAR(40) NOT NULL DEFAULT 'seed_demo'")
        if "confiabilidad" not in consumo_columns:
            missing_consumo_columns.append("ADD COLUMN confiabilidad FLOAT NULL DEFAULT 50")
        if missing_consumo_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE consumo_energetico "
                        + ", ".join(missing_consumo_columns)
                    )
                )

    if inspector.has_table("predicciones"):
        pred_columns = {column["name"] for column in inspector.get_columns("predicciones")}
        missing_pred_columns = []
        if "escenario" not in pred_columns:
            missing_pred_columns.append("ADD COLUMN escenario VARCHAR(20) NOT NULL DEFAULT 'demo'")
        if "origen_dato" not in pred_columns:
            missing_pred_columns.append("ADD COLUMN origen_dato VARCHAR(40) NOT NULL DEFAULT 'modelo_hibrido'")
        if "confiabilidad_datos" not in pred_columns:
            missing_pred_columns.append("ADD COLUMN confiabilidad_datos FLOAT NULL DEFAULT 50")
        if missing_pred_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE predicciones "
                        + ", ".join(missing_pred_columns)
                    )
                )

    if inspector.has_table("recomendaciones"):
        rec_columns = {column["name"] for column in inspector.get_columns("recomendaciones")}
        missing_rec_columns = []
        if "escenario" not in rec_columns:
            missing_rec_columns.append("ADD COLUMN escenario VARCHAR(20) NOT NULL DEFAULT 'demo'")
        if "origen_dato" not in rec_columns:
            missing_rec_columns.append("ADD COLUMN origen_dato VARCHAR(40) NOT NULL DEFAULT 'reglas'")
        if "confiabilidad_datos" not in rec_columns:
            missing_rec_columns.append("ADD COLUMN confiabilidad_datos FLOAT NULL DEFAULT 50")
        if missing_rec_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE recomendaciones "
                        + ", ".join(missing_rec_columns)
                    )
                )
