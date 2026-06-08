"""
tests/test_model.py
===================
Pruebas unitarias que corre la etapa 'test' del pipeline de GitHub Actions.

Pruebas obligatorias del enunciado:
    1. test_modelo_responde_con_shape_correcta
       Verifica que el modelo responde con datos de entrada definidos.

    2. test_accuracy_supera_umbral
       Verifica que la métrica (accuracy) no degrada por debajo del umbral.
       Si falla, el pipeline se detiene y el modelo NO se despliega.
       Esto es el QUALITY GATE: la decisión automatica de "este modelo NO
       merece estar en produccion".

Prueba adicional (bonus, robustez):
    3. test_modelo_no_produce_nan_ni_inf
       Verifica que la salida del modelo es numéricamente sana.

Estas pruebas importan SOLO de app/model_utils.py (no de main.py), así no
requieren levantar FastAPI ni conectarse a Azure. Corren en segundos.

Los datos de prueba se descargan ANTES de correr las pruebas (en el step
previo del workflow). Aqui asumimos que existen en TEST_DATA_PATH.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from app.model_utils import load_model, predict, softmax, top_class


# --- Configuración por variables de entorno --------------------------------
# Permite que el pipeline use rutas distintas (artifacts/...) y que en local
# uses tus archivos (mnist-12.onnx en la raíz, datos descargados a mano).
MODEL_PATH = os.getenv("MODEL_PATH", "mnist-12.onnx")
TEST_DATA_PATH = os.getenv("TEST_DATA_PATH", "mnist_test_subset.npz")
ACCURACY_THRESHOLD = float(os.getenv("ACCURACY_THRESHOLD", "0.90"))


# --- Fixtures: recursos compartidos entre pruebas --------------------------
# Un fixture es una función que pytest ejecuta UNA SOLA VEZ por test (o por
# sesión si usamos scope='session') y "inyecta" su resultado en las pruebas
# que la pidan como parámetro. Evita recargar el modelo en cada test.

@pytest.fixture(scope="session")
def session():
    """Carga el modelo ONNX una sola vez para toda la sesión de pruebas."""
    if not os.path.isfile(MODEL_PATH):
        pytest.fail(
            f"Modelo no encontrado en {MODEL_PATH}. "
            "Asegúrate de descargarlo desde el Blob antes de correr tests."
        )
    return load_model(MODEL_PATH)


@pytest.fixture(scope="session")
def test_data():
    """Carga el subset de MNIST una sola vez para toda la sesión."""
    if not os.path.isfile(TEST_DATA_PATH):
        pytest.fail(
            f"Datos de prueba no encontrados en {TEST_DATA_PATH}. "
            "Asegúrate de descargarlos desde el Blob antes de correr tests."
        )
    data = np.load(TEST_DATA_PATH)
    return data["X"], data["y"]  # X: (N,28,28) uint8, y: (N,) int64


# --- PRUEBA 1 (obligatoria): el modelo responde con datos definidos -------

def test_modelo_responde_con_shape_correcta(session):
    """
    PRUEBA 1 del enunciado:
    Verifica que el modelo responde con datos de entrada definidos.

    Le pasamos un tensor de ceros con la forma exacta que el modelo espera
    y validamos que la salida tiene la forma esperada (1, 10) y tipo float32.

    Si esta prueba falla, significa que el modelo .onnx descargado del Blob
    está corrupto, tiene una firma distinta, o algo cambió fundamentalmente.
    """
    # Entrada determinística: un tensor de ceros con la forma correcta.
    x = np.zeros((1, 1, 28, 28), dtype=np.float32)

    # Inferencia
    logits = predict(session, x)

    # Validaciones de contrato:
    assert logits.shape == (1, 10), (
        f"El modelo debe devolver shape (1, 10), recibió {logits.shape}"
    )
    assert logits.dtype == np.float32, (
        f"El modelo debe devolver float32, recibió {logits.dtype}"
    )


# --- PRUEBA 2 (obligatoria): quality gate por métrica ---------------------

def test_accuracy_supera_umbral(session, test_data):
    """
    PRUEBA 2 del enunciado:
    Verifica que el accuracy del modelo sobre el set de prueba está por
    encima del umbral configurado. Si no, el pipeline FALLA y el modelo
    NO se despliega.

    Esta es la prueba MÁS IMPORTANTE del pipeline:
        - Si alguien sube un modelo entrenado a medias o corrupto, esta
          prueba lo detecta y bloquea el despliegue.
        - El umbral es configurable por entorno: dev=0.90, prod=0.95.
        - Es el patrón estándar de MLOps llamado 'regression test del modelo'.
    """
    X, y_true = test_data
    n = len(X)

    # Inferencia sobre el set completo, una imagen a la vez.
    # (El modelo MNIST-12 no soporta batch, asi que iteramos.)
    y_pred = np.empty(n, dtype=np.int64)
    for i in range(n):
        # Preprocesamiento manual (sin invocar preprocess() para evitar la
        # heurística de inversión, que aquí no aplica: los datos vienen ya
        # en formato MNIST canónico, fondo negro / dígito blanco).
        img = X[i].astype(np.float32) / 255.0       # normalizar [0,1]
        tensor = img.reshape(1, 1, 28, 28)          # forma (1,1,28,28)
        logits = predict(session, tensor)
        probs = softmax(logits)
        digit, _ = top_class(probs)
        y_pred[i] = digit

    accuracy = float(np.mean(y_pred == y_true))

    # El assert con mensaje claro ayuda al diagnóstico en el log del pipeline.
    assert accuracy >= ACCURACY_THRESHOLD, (
        f"Accuracy={accuracy:.4f} por debajo del umbral {ACCURACY_THRESHOLD}. "
        f"El modelo NO cumple el quality gate. Despliegue bloqueado."
    )

    # Pequeño print para que aparezca en el log del pipeline cuando pase.
    print(f"\n  Accuracy del modelo: {accuracy:.4f} (umbral {ACCURACY_THRESHOLD})")


# --- PRUEBA 3 (bonus): no NaN ni Inf en la salida -------------------------

def test_modelo_no_produce_nan_ni_inf(session, test_data):
    """
    PRUEBA 3 (bonus, robustez):
    Verifica que el modelo produce salidas numéricamente sanas sobre datos
    reales, en NINGUNA de las imágenes del set de prueba.

    Un modelo bien entrenado nunca debería producir NaN o Inf, pero si el
    archivo .onnx se corrompió o se entrenó con bugs, esto los detecta.
    """
    X, _ = test_data
    for i in range(len(X)):
        img = X[i].astype(np.float32) / 255.0
        tensor = img.reshape(1, 1, 28, 28)
        logits = predict(session, tensor)
        assert not np.isnan(logits).any(), f"NaN en logits de imagen {i}"
        assert not np.isinf(logits).any(), f"Inf en logits de imagen {i}"
