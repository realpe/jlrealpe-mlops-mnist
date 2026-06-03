#!/usr/bin/env python3
# =============================================================================
# scripts/download_from_blob.py
# -----------------------------------------------------------------------------
# Script que SI usa el pipeline. Se ejecuta en la etapa "test" (y en el build)
# para traer desde Azure Blob Storage:
#   - el modelo mnist-12.onnx  (contenedor "models")
#   - los datos de prueba       (contenedor "data")
#
# Los deja en rutas locales (ej: ./artifacts/model.onnx, ./artifacts/data/)
# para que las pruebas y la construccion de la imagen los puedan usar.
#
# Lee la referencia del modelo desde variables de entorno (nombre del blob,
# contenedor, connection string) -> cumple "solo una referencia en el codigo".
#
# Uso:
#   python scripts/download_from_blob.py
# =============================================================================

# TODO: implementar en el siguiente paso del proyecto.
