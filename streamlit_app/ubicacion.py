"""Ubicación de la instalación para los textos de la interfaz (mismas variables LOCATION_* que la API)."""
import os

NOMBRE = os.getenv("LOCATION_NAME", "Fonseca, La Guajira")
CIUDAD = NOMBRE.split(",")[0].strip() or NOMBRE
LAT = float(os.getenv("LOCATION_LAT", "10.8858"))
LON = float(os.getenv("LOCATION_LON", "-72.8481"))
