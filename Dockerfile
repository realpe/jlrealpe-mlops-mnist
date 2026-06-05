# =============================================================================
# Dockerfile
# -----------------------------------------------------------------------------
# Imagen para servir la API FastAPI con el modelo MNIST en Azure Container Apps.
#
# DECISIONES TECNICAS CLAVE:
#
# 1. Multi-stage build:
#    - Stage 'builder' descarga el modelo desde Azure Blob (necesita secret).
#    - Stage 'runtime' copia el modelo descargado pero NO el secret.
#    Esto garantiza que la connection string nunca quede en la imagen final
#    (auditable con 'docker history').
#
# 2. Imagen base 'python:3.11-slim':
#    Balance entre tamaño (~150 MB) y compatibilidad con wheels precompilados
#    de numpy/pillow/onnxruntime. Evita el dolor de cabeza de Alpine + musl.
#
# 3. Usuario no-root 'appuser':
#    La app corre como usuario sin privilegios. Si la app es comprometida,
#    el atacante NO tiene root dentro del contenedor.
#
# 4. Layer caching óptimo:
#    Copiamos requirements.txt y hacemos pip install ANTES de copiar el código.
#    Asi, cambios en el código no invalidan el cache de las dependencias
#    (build mucho más rápido en cada iteración del pipeline).
# =============================================================================


# =============================================================================
# STAGE 1: builder - descarga el modelo desde Azure Blob
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Argumento de build para recibir la connection string SOLO durante el build.
# Se pasa con: docker build --build-arg AZURE_STORAGE_CONNECTION_STRING="..." .
# IMPORTANTE: --build-arg NO queda en la imagen final si se usa en multi-stage
# y la stage final no lo importa (que es nuestro caso).
ARG AZURE_STORAGE_CONNECTION_STRING

# Instalar SOLO lo necesario para descargar el modelo (no toda la app).
# Esto mantiene el stage 'builder' pequeño y rápido.
RUN pip install --no-cache-dir azure-storage-blob==12.23.1

# Copiar el script de descarga
COPY scripts/download_from_blob.py ./

# Descargar el modelo (NO los datos de prueba, esos solo se usan en pytest).
# El script lee AZURE_STORAGE_CONNECTION_STRING del entorno, asi que la
# exportamos desde el ARG.
RUN AZURE_STORAGE_CONNECTION_STRING="${AZURE_STORAGE_CONNECTION_STRING}" \
    python download_from_blob.py --only model --dest /build/


# =============================================================================
# STAGE 2: runtime - imagen final, sin secretos
# =============================================================================
FROM python:3.11-slim AS runtime

# --- Variables de entorno de Python para mejor comportamiento en containers ---
# PYTHONDONTWRITEBYTECODE=1 -> no crear archivos .pyc (no aportan en contenedor inmutable)
# PYTHONUNBUFFERED=1       -> stdout/stderr sin buffer (logs en tiempo real)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODEL_PATH=/app/model.onnx

# --- Crear usuario no-root ---
# -r = system user (sin home directory ni shell de login)
# -u 1000 = UID predecible (útil para volúmenes y permisos)
RUN groupadd -r appgroup && useradd -r -u 1000 -g appgroup appuser

WORKDIR /app

# --- Instalar dependencias ANTES del código (layer cache friendly) ---
# Si solo cambia el código pero no requirements.txt, esta layer se reusa.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Copiar el modelo desde el stage builder ---
# Importante: solo el archivo del modelo, NADA más del builder.
# El secret AZURE_STORAGE_CONNECTION_STRING NO viaja a esta stage.
COPY --from=builder /build/mnist-12.onnx /app/model.onnx

# --- Copiar el código de la app ---
COPY app/ ./app/

# --- Permisos: dar al usuario no-root acceso a la carpeta de la app ---
RUN chown -R appuser:appgroup /app

# --- Cambiar al usuario no-root para todo lo que viene después ---
USER appuser

# --- Documentación del puerto (no abre nada, solo declara intención) ---
EXPOSE 8000

# --- Healthcheck propio del contenedor ---
# Útil si la imagen se ejecuta fuera de Container Apps (Container Apps usa
# su propio probe externo configurado al crear el app).
# --start-period=10s: dar tiempo a que la app cargue el modelo antes de probar.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

# --- Arrancar uvicorn ---
# --host 0.0.0.0: aceptar conexiones desde fuera del contenedor (no solo localhost)
# --port 8000: coincide con --target-port que configuramos en Container Apps
# --workers 1: una sola réplica del proceso. Container Apps maneja el scaling
#              creando más réplicas del contenedor, no más workers del proceso.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
