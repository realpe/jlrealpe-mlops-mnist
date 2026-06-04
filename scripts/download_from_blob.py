#!/usr/bin/env python3
"""
scripts/download_from_blob.py
=============================
Descarga los artefactos del Azure Blob Storage al sistema de archivos local.

Este script SÍ es parte del pipeline (lo invoca GitHub Actions en la etapa
'test', y también el Dockerfile durante el 'build' para hornear el modelo
dentro de la imagen).

Casos de uso:
    1. Etapa 'test' del pipeline -> descarga modelo + datos para pytest.
    2. Etapa 'build' del Dockerfile -> descarga modelo para incluirlo en la imagen.
    3. Desarrollo local -> opcional, podés correrlo en tu Mac para refrescar
       el modelo o los datos sin tener que descargarlos manualmente.

Uso:
    export AZURE_STORAGE_CONNECTION_STRING="<tu connection string>"

    # Descargar TODO (modelo + datos):
    python scripts/download_from_blob.py

    # Descargar SOLO el modelo (caso típico en el Dockerfile):
    python scripts/download_from_blob.py --only model

    # Descargar SOLO los datos:
    python scripts/download_from_blob.py --only data

    # Especificar carpeta de destino:
    python scripts/download_from_blob.py --dest artifacts/
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    from azure.storage.blob import BlobServiceClient
except ImportError:
    sys.exit("Falta azure-storage-blob. Instalá con: pip install azure-storage-blob")


# --- Configuración por variables de entorno --------------------------------
CONN_STR = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")

MODEL_BLOB_CONTAINER = os.getenv("MODEL_BLOB_CONTAINER", "models")
MODEL_BLOB_NAME = os.getenv("MODEL_BLOB_NAME", "mnist-12.onnx")

DATA_BLOB_CONTAINER = os.getenv("DATA_BLOB_CONTAINER", "data")
DATA_BLOB_NAME = os.getenv("DATA_BLOB_NAME", "mnist_test_subset.npz")


def download_blob(service: BlobServiceClient, container: str, blob_name: str, dest_path: Path) -> None:
    """Descarga un blob a una ruta local. Sobrescribe si ya existía."""
    print(f"Descargando {container}/{blob_name} -> {dest_path} ... ", end="", flush=True)

    blob_client = service.get_blob_client(container=container, blob=blob_name)

    # Si el blob no existe en Azure, fallar rápido con mensaje claro.
    if not blob_client.exists():
        sys.exit(
            f"\nERROR: el blob '{blob_name}' NO existe en el contenedor "
            f"'{container}'. Subilo primero con scripts/upload_to_blob.py."
        )

    # Crear directorio destino si no existe (ej: artifacts/)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # Streaming download (no carga todo en memoria, eficiente para archivos grandes)
    with open(dest_path, "wb") as f:
        stream = blob_client.download_blob()
        f.write(stream.readall())

    size_kb = dest_path.stat().st_size / 1024
    print(f"OK ({size_kb:.1f} KB)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Descargar modelo y/o datos desde Azure Blob Storage.")
    parser.add_argument(
        "--only",
        choices=["model", "data", "all"],
        default="all",
        help="Qué descargar (default: all).",
    )
    parser.add_argument(
        "--dest",
        default=".",
        help="Carpeta de destino (default: directorio actual).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not CONN_STR:
        sys.exit(
            "ERROR: AZURE_STORAGE_CONNECTION_STRING no está definida.\n"
            "En el pipeline esto viene del GitHub Secret del mismo nombre.\n"
            "En local, exportá manualmente con:\n"
            "    export AZURE_STORAGE_CONNECTION_STRING=\"<tu valor>\""
        )

    service = BlobServiceClient.from_connection_string(CONN_STR)
    dest = Path(args.dest)

    print(f"Conectado a Storage Account: {service.account_name}")
    print(f"Destino local: {dest.resolve()}")
    print("-" * 60)

    if args.only in ("model", "all"):
        download_blob(service, MODEL_BLOB_CONTAINER, MODEL_BLOB_NAME, dest / MODEL_BLOB_NAME)

    if args.only in ("data", "all"):
        download_blob(service, DATA_BLOB_CONTAINER, DATA_BLOB_NAME, dest / DATA_BLOB_NAME)

    print("-" * 60)
    print("Descarga completa.")


if __name__ == "__main__":
    main()
