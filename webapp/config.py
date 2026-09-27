"""Configuración central del motor de Gestión de Riesgo (OLG).
Todo lo sensible (endpoints, keys, cadenas de conexión) se lee de variables
de entorno para que nunca quede escrito en el código ni suba a Azure."""
import os

# --- OCR / Azure AI Document Intelligence (producción) ---
AZURE_DI_ENDPOINT = os.getenv("AZURE_DI_ENDPOINT", "")      # https://<recurso>.cognitiveservices.azure.com/
AZURE_DI_KEY      = os.getenv("AZURE_DI_KEY", "")           # o usar Managed Identity (ver azure_provider)
AZURE_DI_MODELO   = os.getenv("AZURE_DI_MODELO", "prebuilt-layout")
AZURE_DI_LOCALE   = os.getenv("AZURE_DI_LOCALE", "es")

# --- Almacenamiento (Blob) ---
AZURE_BLOB_CONN   = os.getenv("AZURE_BLOB_CONN", "")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "expedientes")

# --- OCR local (pruebas / respaldo sin Azure) ---
TESSDATA_DIR = os.getenv("TESSDATA_PREFIX", "/tmp/tessdata")
OCR_IDIOMAS  = os.getenv("OCR_IDIOMAS", "spa")
OCR_DPI      = int(os.getenv("OCR_DPI", "220"))

# Umbral de confianza de OCR por debajo del cual un hallazgo pasa de
# ROJO (confirmado) a AMARILLO (por revisar) — tal como pidió el usuario.
UMBRAL_CONFIANZA_OCR = float(os.getenv("UMBRAL_CONFIANZA_OCR", "0.72"))
