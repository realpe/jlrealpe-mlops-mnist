#!/usr/bin/env python3
# =============================================================================
# scripts/upload_to_blob.py
# -----------------------------------------------------------------------------
# Script de PREPARACION (se corre UNA VEZ, manualmente, desde tu maquina).
# NO es parte del pipeline automatico.
#
# Que hace:
#   1. Sube el archivo mnist-12.onnx al contenedor "models" del Blob Storage.
#   2. Sube los datos de prueba (imagenes/labels de MNIST) al contenedor "data".
#
# Asi se cumple el requisito del enunciado: el .onnx y los datos NO viven en
# el repo de GitHub, sino en el bucket (Azure Blob), y el pipeline los descarga.
#
# Uso:
#   python scripts/upload_to_blob.py
# (requiere la variable de entorno AZURE_STORAGE_CONNECTION_STRING)
# =============================================================================

# TODO: implementar en el siguiente paso del proyecto.
