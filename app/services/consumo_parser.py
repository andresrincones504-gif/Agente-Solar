"""
Servicio de procesamiento de archivos CSV/Excel para consumo energético.
Formato esperado:
- fecha (YYYY-MM-DD o YYYY-MM-DD HH:MM:SS)
- consumo_kwh (float)
- costo_cop (float, opcional)
- demanda_pico_kw (float, opcional)
- produccion_solar_kwh (float, opcional)
- nivel_bateria_pct (float, opcional)
"""
import pandas as pd
from io import BytesIO
from typing import List, Dict, Tuple
from datetime import datetime


COLUMNAS_REQUERIDAS = {"fecha", "consumo_kwh"}
COLUMNAS_OPCIONALES = {
    "costo_cop",
    "demanda_pico_kw",
    "produccion_solar_kwh",
    "nivel_bateria_pct",
    "periodo",
}


class ConsumoFileParser:
    @staticmethod
    def parse_file(
        contenido: bytes,
        filename: str,
    ) -> Tuple[List[Dict], List[str]]:
        """
        Parsea archivo y retorna (registros_validos, errores).
        """
        errores: List[str] = []
        nombre_lower = filename.lower()

        try:
            if nombre_lower.endswith(".csv"):
                df = pd.read_csv(BytesIO(contenido))
            elif nombre_lower.endswith((".xlsx", ".xls")):
                df = pd.read_excel(BytesIO(contenido), engine="openpyxl")
            else:
                return [], ["Formato no soportado. Use CSV o XLSX."]
        except Exception as e:
            return [], [f"Error leyendo archivo: {e}"]

        # Normalizar nombres de columna
        df.columns = [str(c).strip().lower() for c in df.columns]

        # Validar columnas requeridas
        faltantes = COLUMNAS_REQUERIDAS - set(df.columns)
        if faltantes:
            return [], [
                f"Columnas requeridas faltantes: {', '.join(faltantes)}. "
                f"El archivo debe tener al menos: {', '.join(COLUMNAS_REQUERIDAS)}"
            ]

        # Procesar filas
        registros = []
        for idx, row in df.iterrows():
            fila = idx + 2  # +2 por header y base 1
            try:
                fecha = pd.to_datetime(row["fecha"])
                if pd.isna(fecha):
                    errores.append(f"Fila {fila}: fecha inválida")
                    continue

                consumo = float(row["consumo_kwh"])
                if consumo < 0:
                    errores.append(f"Fila {fila}: consumo_kwh negativo")
                    continue

                rec = {
                    "fecha": fecha.to_pydatetime(),
                    "consumo_kwh": consumo,
                    "periodo": str(row.get("periodo", "diario")).lower(),
                }

                # Opcionales
                for campo in ("costo_cop", "demanda_pico_kw", "produccion_solar_kwh", "nivel_bateria_pct"):
                    if campo in df.columns:
                        val = row.get(campo)
                        if pd.notna(val):
                            rec[campo] = float(val)

                registros.append(rec)
            except (ValueError, TypeError) as e:
                errores.append(f"Fila {fila}: {e}")

        return registros, errores


parser = ConsumoFileParser()
