# =============================================================================
# Dockerfile
# -----------------------------------------------------------------------------
# Construye la imagen del contenedor que se desplegara en Azure Container Apps.
#
# Pasos que tendra:
#   1. Partir de una imagen base liviana de Python (ej: python:3.11-slim).
#   2. Instalar dependencias desde requirements.txt.
#   3. Copiar el codigo de la carpeta app/ y los scripts/.
#   4. Durante el build, descargar el modelo .onnx desde el Blob
#      (el .onnx NO se copia desde el repo porque no existe ahi).
#   5. Exponer el puerto y arrancar uvicorn sirviendo app.main:app.
#
# Decision: imagen 'slim' en vez de la completa -> imagen mas pequena,
# build mas rapido, menos consumo. MNIST es minusculo asi que sobra.
# =============================================================================

# TODO: implementar en el siguiente paso del proyecto.
