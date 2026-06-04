#!/usr/bin/env python3
"""
scripts/prepare_test_data.py
============================
Genera un archivo .npz con un subset pequeño de MNIST para las pruebas
unitarias del pipeline. Se ejecuta UNA SOLA VEZ, manualmente, desde tu
máquina. El resultado (mnist_test_subset.npz) se sube luego al Blob
(contenedor 'data') con el script upload_to_blob.py.

Por qué un subset y no el dataset completo:
    - El test del pipeline debe ser RÁPIDO (segundos, no minutos).
    - 100 imágenes son suficientes para detectar regresiones del modelo.
    - El archivo final pesa ~50 KB en lugar de ~10 MB.

Por qué NO incluir esto en el repo:
    - El enunciado prohíbe que los datos vivan en el repo; deben venir del bucket.
    - Por eso este script genera el archivo localmente y luego se sube al Blob.

Requisitos:
    pip install tensorflow-datasets numpy
    (o alternativa con torchvision, ver al final del script)
"""

import os

import numpy as np


def generate_subset(n_samples: int = 100, output_path: str = "mnist_test_subset.npz") -> None:
    """
    Descarga el set de validación de MNIST y guarda un subset aleatorio
    como .npz con dos arrays: 'X' (imágenes) y 'y' (labels).

    Forma final:
        X: (n_samples, 28, 28)  uint8, valores 0-255 (sin normalizar)
        y: (n_samples,)         int64, valores 0-9

    Nota: NO normalizamos a [0,1] aquí. La normalización vive en preprocess()
    de app/model_utils.py para mantener una sola fuente de verdad.
    """
    # Usamos keras (viene con tensorflow) porque es la forma estándar y
    # confiable de obtener MNIST. La alternativa con torchvision funciona
    # igual; la incluyo como comentario al final.
    try:
        from tensorflow.keras.datasets import mnist
    except ImportError:
        raise ImportError(
            "Falta tensorflow. Instalalo con: pip install tensorflow\n"
            "Alternativa: usa torchvision (descomenta el bloque al final del script)."
        )

    print("Descargando MNIST (primera vez puede tomar 1-2 minutos)...")
    (_, _), (X_test, y_test) = mnist.load_data()
    print(f"   Dataset de test cargado: X.shape={X_test.shape}, y.shape={y_test.shape}")

    # Seed fijo para reproducibilidad: el mismo subset siempre.
    # Esto es CRÍTICO para que el quality gate del pipeline sea determinista.
    rng = np.random.default_rng(seed=42)
    idx = rng.choice(len(X_test), size=n_samples, replace=False)
    X_subset = X_test[idx]
    y_subset = y_test[idx]

    np.savez(output_path, X=X_subset, y=y_subset)
    print(f"Subset guardado en {output_path}")
    print(f"   Tamaño en disco: {os.path.getsize(output_path) / 1024:.1f} KB")
    print(f"   Distribución de clases: {np.bincount(y_subset, minlength=10)}")


if __name__ == "__main__":
    generate_subset(n_samples=100, output_path="mnist_test_subset.npz")

# -----------------------------------------------------------------------------
# Alternativa sin tensorflow (con torchvision):
# -----------------------------------------------------------------------------
# from torchvision import datasets
# ds = datasets.MNIST(root=".", train=False, download=True)
# X_test = ds.data.numpy()      # (10000, 28, 28) uint8
# y_test = ds.targets.numpy()   # (10000,) int64
# -----------------------------------------------------------------------------
