"""
app/main.py
===========
API REST construida con FastAPI que sirve el modelo MNIST.

Endpoints:
    GET  /         -> info básica del servicio (útil para la demo)
    GET  /health   -> health check para Azure Container Apps
    POST /predict  -> recibe una imagen, devuelve digit + confidence

Comportamiento al arrancar (lifespan):
    1. Lee variables de entorno (MODEL_PATH, ENVIRONMENT, conexión a Blob).
    2. Carga el modelo ONNX desde disco (la imagen Docker ya lo trae adentro).
    3. Inicializa el cliente del Append Blob para registrar predicciones.
    4. Si la connection string de Azure no está, entra en MODO LOCAL: la API
       funciona pero NO escribe predicciones al Blob (útil para desarrollar
       en local sin Azure).
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.model_utils import load_model, preprocess, predict, softmax, top_class


# --- Configuración por variables de entorno ----------------------------------
# Todas las configuraciones vienen de variables de entorno, NUNCA hardcodeadas.
# Esto permite que la misma imagen Docker sirva para dev y prod, sin recompilar:
# solo cambian las variables que se le pasan al Container App.

MODEL_PATH = os.getenv("MODEL_PATH", "/app/model.onnx")
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")   # "dev" o "prod"
PREDICTIONS_CONTAINER = os.getenv("PREDICTIONS_CONTAINER", "predictions")
PREDICTIONS_BLOB_NAME = f"predicciones_{ENVIRONMENT}.txt"
AZURE_CONN_STR = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")


# --- Logger -----------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mnist-api")


# --- Estado compartido entre peticiones --------------------------------------
# Diccionario que vive durante toda la vida del proceso. Lo llenamos en
# lifespan() al arrancar, y los endpoints lo leen sin recargar nada.
state: dict = {
    "session": None,        # InferenceSession de ONNX
    "blob_client": None,    # cliente del Append Blob (None si no hay Azure)
    "ready": False,         # flag para /health
}


# --- Lifespan: se ejecuta al arrancar y al cerrar la app --------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Inicializa recursos pesados (modelo, cliente Azure) UNA SOLA VEZ al
    arrancar la app, no por cada request. Esto es crítico para performance.

    El bloque ANTES de `yield` corre al arrancar.
    El bloque DESPUÉS de `yield` corre al cerrar (limpieza).
    """
    # ----- ARRANQUE -----
    logger.info("Iniciando aplicación (environment=%s)", ENVIRONMENT)

    # 1. Cargar el modelo ONNX desde disco
    if not os.path.isfile(MODEL_PATH):
        # Si no existe el modelo, la app no puede funcionar. Falla rápido y
        # con mensaje claro (mejor que arrancar y crashear en el primer request).
        raise RuntimeError(
            f"Modelo no encontrado en {MODEL_PATH}. "
            "Verifica que el Dockerfile lo haya descargado en el build, "
            "o que MODEL_PATH apunte al archivo correcto en desarrollo local."
        )
    logger.info("Cargando modelo desde %s", MODEL_PATH)
    state["session"] = load_model(MODEL_PATH)
    logger.info("Modelo cargado correctamente.")

    # 2. Inicializar cliente del Append Blob (si hay credenciales de Azure)
    if AZURE_CONN_STR:
        try:
            # Import diferido: solo importamos azure-storage-blob si lo vamos
            # a usar. Así en MODO LOCAL la app no requiere instalar el SDK.
            from azure.storage.blob import BlobServiceClient

            service = BlobServiceClient.from_connection_string(AZURE_CONN_STR)
            blob_client = service.get_blob_client(
                container=PREDICTIONS_CONTAINER,
                blob=PREDICTIONS_BLOB_NAME,
            )

            # Si el blob no existe todavía, hay que crearlo COMO APPEND BLOB
            # (no como block blob normal, porque luego haremos append_block).
            # exists() es una llamada barata.
            if not blob_client.exists():
                blob_client.create_append_blob()
                logger.info("Append blob creado: %s", PREDICTIONS_BLOB_NAME)
            else:
                logger.info("Append blob ya existe: %s", PREDICTIONS_BLOB_NAME)

            state["blob_client"] = blob_client
        except Exception as e:
            # No queremos que un fallo de Azure impida que la API arranque.
            # Mejor arrancar en modo degradado y avisar.
            logger.error("No se pudo inicializar Append Blob: %s", e)
            logger.warning("La API funcionará SIN registrar predicciones.")
    else:
        logger.warning(
            "AZURE_STORAGE_CONNECTION_STRING vacía -> modo LOCAL (sin Blob)."
        )

    state["ready"] = True
    logger.info("Aplicación lista.")

    yield   # <--- aquí FastAPI atiende peticiones normalmente

    # ----- CIERRE -----
    logger.info("Apagando aplicación.")
    # ONNX Runtime no necesita cierre explícito; el SDK de Azure tampoco.
    # Si en el futuro abrimos conexiones persistentes, aquí se cierran.


# --- Aplicación FastAPI ------------------------------------------------------
app = FastAPI(
    title="MNIST Classifier API",
    description=(
        "API REST que clasifica dígitos manuscritos usando un modelo ONNX. "
        "Proyecto final de la Maestría en IA Aplicada, Universidad Icesi."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# --- Helper para registrar predicciones en el Append Blob -------------------
def log_prediction(digit: int, confidence: float) -> None:
    """
    Escribe una línea JSON con la predicción al Append Blob de Azure.

    Diseñado para ser BEST-EFFORT: si falla por cualquier razón, loggea el
    error pero NO propaga la excepción. Una predicción válida no se debe
    invalidar por un fallo de logging.
    """
    if state["blob_client"] is None:
        # Modo local sin Azure: no hacer nada, no es un error.
        return

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": ENVIRONMENT,
        "digit": digit,
        "confidence": round(confidence, 4),
    }
    line = json.dumps(record) + "\n"

    try:
        # append_block añade los bytes al FINAL del blob de forma atómica.
        # Esto es seguro incluso con escrituras concurrentes (cosa que
        # NO sería seguro con un block blob normal).
        state["blob_client"].append_block(line.encode("utf-8"))
    except Exception as e:
        # Loggear pero NO relanzar. El usuario ya recibió su predicción.
        logger.error("Fallo al escribir predicción en Append Blob: %s", e)


# --- Endpoints ---------------------------------------------------------------

@app.get("/")
async def root():
    """Página de bienvenida con info básica del servicio (útil para la demo)."""
    return {
        "service": "MNIST Classifier API",
        "environment": ENVIRONMENT,
        "version": app.version,
        "docs": "/docs",                # FastAPI auto-genera Swagger en /docs
        "health": "/health",
        "predict": "POST /predict (multipart/form-data with 'file')",
    }


@app.get("/health")
async def health():
    """
    Health check usado por Azure Container Apps para saber si el contenedor
    está vivo y listo para recibir tráfico.

    Si devuelve 200, Container Apps considera la réplica saludable.
    Si devuelve 503, Container Apps no le manda tráfico hasta que se recupere.
    """
    if not state["ready"] or state["session"] is None:
        # 503 Service Unavailable: contenedor arrancando o roto.
        raise HTTPException(status_code=503, detail="Service not ready")
    return {"status": "ok", "environment": ENVIRONMENT}


@app.post("/predict")
async def predict_endpoint(file: UploadFile = File(...)):
    """
    Recibe una imagen (cualquier formato común: PNG, JPG, etc.) y devuelve
    el dígito predicho (0-9) junto con la confianza del modelo.

    La imagen se preprocesa internamente (resize a 28x28, grayscale,
    inversión automática si hace falta) - el usuario puede subir cualquier
    foto razonable de un dígito.
    """
    # --- 1. Validar que sea una imagen ---
    if file.content_type is None or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail=f"Se esperaba una imagen, se recibió content-type={file.content_type}",
        )

    # --- 2. Leer los bytes de la imagen ---
    try:
        image_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo archivo: {e}")

    if not image_bytes:
        raise HTTPException(status_code=400, detail="Archivo vacío.")

    # --- 3. Preprocesar + inferir + postprocesar ---
    try:
        tensor = preprocess(image_bytes)
        logits = predict(state["session"], tensor)
        probs = softmax(logits)
        digit, confidence = top_class(probs)
    except Exception as e:
        # Si algo falla en preprocesamiento o inferencia, es un 500 (error
        # interno) o 400 si la imagen estaba corrupta. Por simplicidad, 400:
        # asumimos que la imagen no era válida.
        logger.error("Error en predicción: %s", e)
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo procesar la imagen: {e}",
        )

    # --- 4. Registrar la predicción (best-effort, no falla la respuesta) ---
    log_prediction(digit, confidence)

    # --- 5. Devolver respuesta ---
    return JSONResponse(
        content={
            "digit": digit,
            "confidence": round(confidence, 4),
            "environment": ENVIRONMENT,
        }
    )
