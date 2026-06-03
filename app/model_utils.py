"""
app/model_utils.py
==================
Funciones puras para inferencia con el modelo MNIST en formato ONNX.

Este módulo está deliberadamente desacoplado de FastAPI: no importa nada de
la API ni tiene estado global. Eso permite que las pruebas unitarias del
pipeline (tests/test_model.py) puedan importar estas funciones directamente
y probarlas sin levantar el servidor web.

Contrato del modelo MNIST (opset 12):
    - Entrada: tensor de forma (1, 1, 28, 28), dtype float32, valores en [0, 1]
      - Fondo NEGRO (cerca de 0), dígito BLANCO (cerca de 1)
    - Salida: tensor de forma (1, 10), float32, logits SIN softmax aplicado
      - Una entrada por cada dígito 0-9
"""

from __future__ import annotations

from io import BytesIO
from typing import Union

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps


# Tipo conveniente: aceptamos bytes (lo que llega por HTTP) o un PIL Image ya abierto.
ImageInput = Union[bytes, Image.Image]


def load_model(model_path: str) -> ort.InferenceSession:
    """
    Crea una InferenceSession de ONNX Runtime a partir de la ruta al .onnx.

    La sesión es el objeto que mantiene el modelo cargado en memoria y permite
    correr inferencias rápidas. Se crea UNA SOLA VEZ al arrancar la app, no
    por cada predicción (cargar el modelo es caro; usarlo es barato).

    Decisión: usamos el provider 'CPUExecutionProvider' explícitamente.
    onnxruntime detecta GPU si está disponible, pero forzar CPU evita warnings
    en entornos sin GPU (Container Apps no tiene GPU en el tier que usamos).
    """
    return ort.InferenceSession(
        model_path,
        providers=["CPUExecutionProvider"],
    )


def preprocess(image_input: ImageInput) -> np.ndarray:
    """
    Convierte una imagen arbitraria al tensor exacto que el modelo MNIST espera.

    Pasos:
      1. Abrir la imagen (si vino como bytes desde HTTP).
      2. Convertir a escala de grises ('L' en PIL = 8-bit grayscale).
      3. Redimensionar a 28x28 píxeles.
      4. Detectar la orientación (fondo claro vs oscuro) e invertir si hace falta.
      5. Normalizar a rango [0.0, 1.0] dividiendo por 255.
      6. Dar forma final (1, 1, 28, 28): batch_size=1, canales=1, alto=28, ancho=28.

    Devuelve: np.ndarray de shape (1, 1, 28, 28), dtype float32.
    """
    # --- 1. Cargar imagen si vino como bytes ---
    if isinstance(image_input, bytes):
        image = Image.open(BytesIO(image_input))
    else:
        image = image_input

    # --- 2. Forzar escala de grises ---
    # El modo 'L' garantiza 1 canal de 8 bits, sin importar si la imagen
    # original era RGB, RGBA o ya grayscale.
    image = image.convert("L")

    # --- 3. Redimensionar a 28x28 ---
    # Image.LANCZOS es un filtro de alta calidad para downscaling, recomendado
    # cuando reducimos drásticamente el tamaño (la entrada del usuario puede
    # ser de 1000x1000 píxeles y hay que llegar a 28x28).
    image = image.resize((28, 28), Image.LANCZOS)

    # --- 4. Detección automática de inversión de colores ---
    # MNIST espera fondo NEGRO (valores cercanos a 0) y dígito BLANCO (cercanos
    # a 255). Si el usuario sube una foto de un dígito en papel (fondo blanco,
    # trazo negro), tenemos que invertir.
    #
    # Heurística simple: si la media de píxeles está más cerca del blanco (>127),
    # el fondo es claro y hay que invertir.
    arr = np.array(image, dtype=np.uint8)
    if arr.mean() > 127:
        image = ImageOps.invert(image)
        arr = np.array(image, dtype=np.uint8)

    # --- 5. Normalizar a [0.0, 1.0] ---
    # El modelo fue entrenado con valores en este rango, no en [0, 255].
    # Si nos olvidáramos de esta línea, las predicciones serían basura aunque
    # todo lo demás estuviera bien.
    arr_float = arr.astype(np.float32) / 255.0

    # --- 6. Dar forma (1, 1, 28, 28) ---
    # El modelo espera batch_size=1 (procesa una imagen a la vez) y 1 canal
    # (grayscale). np.reshape no copia memoria, solo cambia la "vista".
    tensor = arr_float.reshape(1, 1, 28, 28)

    return tensor


def predict(session: ort.InferenceSession, x: np.ndarray) -> np.ndarray:
    """
    Corre la inferencia sobre el tensor preprocesado.

    Devuelve los LOGITS crudos, shape (1, 10), float32.
    Atención: estos NO son probabilidades — el modelo MNIST no aplica softmax
    internamente. Para obtener probabilidades hay que pasar el resultado por
    la función `softmax` de abajo.

    Decisión: usamos session.get_inputs()[0].name en vez de hardcodear "Input3"
    (que es el nombre real del input en este modelo). Así, si en el futuro
    cambian el modelo por otro con nombre de input distinto, el código sigue
    funcionando sin tocarlo.
    """
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: x})
    # session.run devuelve una lista (un elemento por cada output del modelo).
    # MNIST tiene un solo output, así que tomamos [0].
    return outputs[0]


def softmax(logits: np.ndarray) -> np.ndarray:
    """
    Convierte logits a probabilidades, de forma numéricamente estable.

    Versión estable: restar el máximo ANTES de exponenciar evita que exp()
    desborde a infinito con logits grandes (ej. exp(800) = inf en float32).
    Matemáticamente equivale a la fórmula clásica, pero sin overflow.

    Trabaja sobre el último eje, así que funciona con shape (1, 10) o (N, 10).
    """
    # axis=-1 significa "el último eje", que en (1,10) son los 10 logits.
    # keepdims=True mantiene la forma para que el broadcasting de la resta funcione.
    shifted = logits - np.max(logits, axis=-1, keepdims=True)
    exp = np.exp(shifted)
    return exp / np.sum(exp, axis=-1, keepdims=True)


def top_class(probs: np.ndarray) -> tuple[int, float]:
    """
    De un vector de probabilidades shape (1, 10), devuelve la clase ganadora
    y su probabilidad.

    Returns:
        (digit, confidence): el dígito predicho (0-9) y su probabilidad (0-1).
    """
    # probs[0] saca el primer (y único) elemento del batch, dejando shape (10,).
    digit = int(np.argmax(probs[0]))
    confidence = float(probs[0][digit])
    return digit, confidence
