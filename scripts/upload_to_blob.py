#!/usr/bin/env python3
"""
scripts/upload_to_blob.py
=========================
Sube los artefactos del proyecto al Azure Blob Storage.

Se ejecuta MANUALMENTE desde tu máquina, NO desde el pipeline. Es un script
de mantenimiento que reemplaza los comandos sueltos de `az storage blob upload`
con un proceso reproducible y versionado en el repo.

Cuándo ejecutarlo:
    - Después de descargar/regenerar mnist-12.onnx (modelo nuevo).
    - Después de regenerar mnist_test_subset.npz (datos de prueba nuevos).
    - Al provisionar el proyecto en una nueva suscripción de Azure.

Uso:
    export AZURE_STORAGE_CONNECTION_STRING="<tu connection string>"
    python scripts/upload_to_blob.py

Variables de entorno opcionales (con sus defaults):
    MODEL_LOCAL_PATH        = "mnist-12.onnx"
    MODEL_BLOB_CONTAINER    = "models"
    MODEL_BLOB_NAME         = "mnist-12.onnx"
    DATA_LOCAL_PATH         = "mnist_test_subset.npz"
    DATA_BLOB_CONTAINER     = "data"
    DATA_BLOB_NAME          = "mnist_test_subset.npz"
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Import diferido del SDK de Azure: si falta, mensaje claro de cómo instalarlo.
try:
    from azure.storage.blob import BlobServiceClient
except ImportError:
    sys.exit(
        "Falta azure-storage-blob. Instalá con:\n"
        "    pip install azure-storage-blob"
    )


# --- Configuración por variables de entorno --------------------------------
CONN_STR = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")

MODEL_LOCAL_PATH = os.getenv("MODEL_LOCAL_PATH", "mnist-12.onnx")
MODEL_BLOB_CONTAINER = os.getenv("MODEL_BLOB_CONTAINER", "models")
MODEL_BLOB_NAME = os.getenv("MODEL_BLOB_NAME", "mnist-12.onnx")

DATA_LOCAL_PATH = os.getenv("DATA_LOCAL_PATH", "mnist_test_subset.npz")
DATA_BLOB_CONTAINER = os.getenv("DATA_BLOB_CONTAINER", "data")
DATA_BLOB_NAME = os.getenv("DATA_BLOB_NAME", "mnist_test_subset.npz")


def upload_blob(service: BlobServiceClient, container: str, blob_name: str, local_path: str) -> None:
    """
    Sube un archivo local al Blob. Sobrescribe si ya existía.

    Decisión: usamos overwrite=True por simplicidad y porque este script es
    para mantenimiento - si lo ejecutás de nuevo, generalmente es porque
    querés reemplazar la versión vieja. La alternativa más segura sería
    versionar los blobs (Blob versioning de Azure), pero añade complejidad.
    """
    local_file = Path(local_path)
    if not local_file.is_file():
        sys.exit(f"ERROR: archivo local no encontrado: {local_path}")

    size_kb = local_file.stat().st_size / 1024
    print(f"Subiendo {local_path} ({size_kb:.1f} KB) -> {container}/{blob_name} ... ", end="", flush=True)

    blob_client = service.get_blob_client(container=container, blob=blob_name)
    with open(local_file, "rb") as f:
        blob_client.upload_blob(f, overwrite=True)

    print("OK")


def main() -> None:
    # Validar credenciales
    if not CONN_STR:
        sys.exit(
            "ERROR: AZURE_STORAGE_CONNECTION_STRING no está definida.\n"
            "Exportala con:\n"
            "    export AZURE_STORAGE_CONNECTION_STRING=\"<tu valor>\""
        )

    # Crear cliente UNA VEZ y reusarlo (más eficiente que crear uno por blob)
    service = BlobServiceClient.from_connection_string(CONN_STR)

    print(f"Conectado a Storage Account: {service.account_name}")
    print("-" * 60)

    upload_blob(service, MODEL_BLOB_CONTAINER, MODEL_BLOB_NAME, MODEL_LOCAL_PATH)
    upload_blob(service, DATA_BLOB_CONTAINER, DATA_BLOB_NAME, DATA_LOCAL_PATH)

    print("-" * 60)
    print("Subida completa.")


if __name__ == "__main__":
    main()
