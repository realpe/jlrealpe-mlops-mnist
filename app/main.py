# =============================================================================
# app/main.py
# -----------------------------------------------------------------------------
# Aplicacion FastAPI que sirve el modelo MNIST en formato ONNX.
#
# Responsabilidades de este archivo (se implementaran en el siguiente paso):
#   1. Al arrancar, descargar el modelo .onnx desde Azure Blob Storage
#      (NO viene dentro de la imagen ni del repo; se obtiene en runtime/build).
#   2. Cargar el modelo con onnxruntime (crear la InferenceSession una sola vez).
#   3. Exponer endpoints:
#        - GET  /health   -> chequeo de vida (util para Container Apps).
#        - POST /predict   -> recibe una imagen, devuelve el digito predicho.
#   4. Despues de cada prediccion, registrar una linea en el archivo de
#      predicciones (predicciones_dev.txt o predicciones_prod.txt) usando
#      un Append Blob en Azure (escritura segura ante concurrencia).
#
# La variable de entorno ENVIRONMENT (dev/prod) decide a que archivo .txt
# se escriben las predicciones.
# =============================================================================

# TODO: implementar en el siguiente paso del proyecto.
