# Sistema de Despliegue Automático de Modelos ONNX (MLOps)

> **Proyecto Final** — Maestría en IA Aplicada, Universidad Icesi
> **Estudiante:** José Luis Realpe Manrique
> **Repositorio:** https://github.com/realpe/jlrealpe-mlops-mnist

Sistema de **CI/CD para despliegue automático** de un modelo de clasificación
de imágenes (MNIST, formato ONNX) sobre Azure Container Apps, con dos entornos
(`dev` y `prod`) y pipeline de GitHub Actions que ejecuta pruebas + build +
deploy en cada `push`.

---

## 1. Problema y solución propuesta

### Problema

En proyectos reales de Machine Learning, un modelo entrenado no aporta valor
hasta que esté **desplegado y disponible** para los usuarios. Cada vez que se
entrena una nueva versión del modelo, el equipo necesita:

1. Verificar que el nuevo modelo no degrada en métricas clave respecto al
   anterior (*quality gate*).
2. Empaquetarlo en una forma consumible (API REST, contenedor).
3. Desplegarlo de forma controlada en un entorno de pruebas (`dev`) antes de
   promoverlo a producción (`prod`).
4. Mantener trazabilidad de qué predicciones hizo el modelo en cada entorno.

Hacer esto manualmente es lento, propenso a errores, y rompe la idea de
*continuous deployment*.

### Solución

Pipeline de CI/CD que automatiza todo el ciclo:

- El modelo `.onnx` vive en un **bucket** (Azure Blob Storage), no en el repo.
- Cada `push` a `dev` o `prod` dispara un workflow de GitHub Actions que:
  1. **Descarga** el modelo y los datos de prueba desde el bucket.
  2. **Prueba** el modelo con pruebas unitarias (forma de salida, métrica
     mínima de accuracy).
  3. Si pasa, **construye** la imagen Docker con una API FastAPI que sirve el
     modelo.
  4. **Publica** la imagen en GitHub Container Registry (ghcr.io).
  5. **Despliega** actualizando el Container App correspondiente al entorno.
- Cada predicción del endpoint se registra en `predicciones_<env>.txt` dentro
  del bucket, usando **Append Blob** para evitar condiciones de carrera.

---

## 2. Arquitectura

```
┌──────────────┐
│ Desarrollador│  git push (dev | prod)
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────┐
│           GitHub Actions Workflow                │
│                                                  │
│  ┌────────────────┐    ┌──────────────────────┐ │
│  │  Etapa: test   │ →  │ Etapa: build/promote │ │
│  │  - download    │    │  - docker build      │ │
│  │  - pytest      │    │  - push a ghcr.io    │ │
│  │  (2 pruebas)   │    │  - update App        │ │
│  └────────┬───────┘    └──────────┬───────────┘ │
└───────────┼─────────────────────────┼───────────┘
            │ descarga                │ despliega
            ▼                         ▼
   ┌──────────────────┐     ┌──────────────────────┐
   │ Azure Blob       │     │ Azure Container Apps │
   │  - models/       │     │  - mnist-api-dev     │
   │  - data/         │     │  - mnist-api-prod    │
   │  - predictions/  │◄────│  (escala a cero)     │
   └──────────────────┘     └──────────────────────┘
   (mexicocentral)             (eastus2)
```

### Componentes

| Componente | Servicio | Región | Función |
|---|---|---|---|
| Modelo y datos | Azure Blob Storage | mexicocentral | Almacena el `.onnx`, datos de prueba y archivos de predicciones |
| Registro de imágenes | GitHub Container Registry (ghcr.io) | global | Almacena las imágenes Docker construidas por el pipeline |
| Cómputo | Azure Container Apps | eastus2 | Hosting serverless con escala a cero |
| CI/CD | GitHub Actions | — | Pipeline test + build + deploy |
| Modelo | MNIST (ONNX opset 12) | — | Clasificación de dígitos manuscritos 0-9 |
| API | FastAPI | — | Expone `/health` y `/predict` |

---

## 3. Estructura del repositorio

```
.
├── .github/workflows/
│   ├── dev.yml              # Pipeline rama dev (test + build + deploy)
│   └── prod.yml             # Pipeline rama prod (con umbral más estricto)
├── app/
│   ├── __init__.py
│   ├── main.py              # API FastAPI: /health y /predict
│   └── model_utils.py       # Funciones puras: preprocess, predict, softmax
├── tests/
│   ├── __init__.py
│   └── test_model.py        # Las 2 pruebas obligatorias del enunciado
├── scripts/
│   ├── upload_to_blob.py    # Sube modelo+datos al Blob (uso manual, una vez)
│   └── download_from_blob.py# Descarga en el pipeline
├── docs/
│   └── azure-setup.md       # Guía paso a paso de comandos `az`
├── Dockerfile               # Imagen del contenedor
├── requirements.txt         # Dependencias Python (versiones fijadas)
├── .gitignore               # Bloquea *.onnx, .env y secretos
├── .env.example             # Plantilla de variables (sin valores reales)
└── README.md                # Este archivo
```

---

## 4. Flujo de CI/CD

Cada `push` a `dev` o `prod` dispara automáticamente el workflow correspondiente.

### Etapa 1 — `test`

1. Checkout del código.
2. Instalar dependencias (`pip install -r requirements.txt`).
3. Descargar el modelo `.onnx` y los datos de prueba desde Azure Blob Storage
   (script `scripts/download_from_blob.py`, autenticado con
   `AZURE_STORAGE_CONNECTION_STRING`).
4. Correr `pytest tests/` que ejecuta las dos pruebas obligatorias:
   - **Prueba 1:** el modelo responde con datos de entrada definidos (shape
     de salida correcta, sin NaN).
   - **Prueba 2:** la métrica (accuracy sobre el set de prueba) está por
     encima del umbral configurado (`ACCURACY_THRESHOLD`). Si falla, el
     pipeline se detiene y el modelo NO se despliega — esto es el *quality
     gate*.

### Etapa 2 — `build/promote` (solo si `test` pasa)

1. Login a `ghcr.io` usando el `GITHUB_TOKEN` automático.
2. Construir la imagen Docker (descarga el modelo desde el Blob durante el
   build para que viva dentro de la imagen final).
3. Push de la imagen a `ghcr.io/realpe/jlrealpe-mlops-mnist:<env>`.
4. Login a Azure usando el secret `AZURE_CREDENTIALS`.
5. Actualizar el Container App (`mnist-api-dev` o `mnist-api-prod`) para que
   apunte a la nueva imagen.

---

## 5. Endpoints

| Entorno | Rama | URL del endpoint |
|---|---|---|
| dev | `dev` | `https://mnist-api-dev.nicerock-dd1b33cc.eastus2.azurecontainerapps.io` |
| prod | `prod` | `https://mnist-api-prod.nicerock-dd1b33cc.eastus2.azurecontainerapps.io` |

### Endpoints expuestos por la API

- `GET /health` → chequeo de vida del servicio.
- `POST /predict` → recibe una imagen (multipart/form-data), devuelve el
  dígito predicho y la confianza.

Ejemplo de uso:

```bash
curl -X POST "https://mnist-api-dev.<dominio>/predict" \
  -F "file=@mi_digito.png"
# Respuesta: {"digit": 7, "confidence": 0.9823}
```

---

## 6. Cómo ejecutar localmente

Requisitos: Python 3.11+ y el modelo `mnist-12.onnx` descargado localmente
(ver `docs/azure-setup.md` paso 3).

```bash
# Crear y activar entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno (copiar plantilla y editar)
cp .env.example .env
# Editar .env y poner la AZURE_STORAGE_CONNECTION_STRING real

# Correr las pruebas unitarias
pytest tests/ -v

# Levantar la API en local (puerto 8000)
uvicorn app.main:app --reload --port 8000

# Probar el endpoint /health
curl http://localhost:8000/health
```

---

## 7. Configuración en Azure

Toda la configuración de infraestructura está documentada paso a paso en:

📄 **[`docs/azure-setup.md`](docs/azure-setup.md)**

Incluye los comandos `az` exactos para crear el Resource Group, Storage
Account, Container Apps Environment, Container Apps y el Service Principal
para GitHub Actions. También cubre la creación de los GitHub Secrets
necesarios para que el pipeline funcione.

### Secrets requeridos en GitHub

El pipeline necesita estos tres secrets configurados en
*Settings → Secrets and variables → Actions*:

| Secret | Origen |
|---|---|
| `AZURE_CREDENTIALS` | JSON del Service Principal (paso 7 de `azure-setup.md`) |
| `AZURE_STORAGE_CONNECTION_STRING` | Connection string del Storage Account |
| `RESOURCE_GROUP` | Nombre del resource group (`rg-proyecto-mlops`) |

---

## 8. Decisiones técnicas relevantes

Esta sección documenta las decisiones técnicas no obvias del proyecto, con su
justificación. Es información útil para entender por qué la arquitectura tiene
la forma que tiene.

### 8.1 Multi-región: Storage en `mexicocentral`, cómputo en `eastus2`

Azure for Students aplica una política (*Allowed resource deployment regions*)
que restringe las regiones disponibles a un subconjunto. Para esta cuenta:
`southcentralus`, `northcentralus`, `chilecentral`, `mexicocentral`, `eastus2`.

- **Storage en `mexicocentral`:** región más cercana físicamente a Colombia,
  minimiza latencia para subir/descargar el modelo.
- **Container Apps en `eastus2`:** el servicio Container Apps no está
  disponible aún en `mexicocentral`; `eastus2` es la región madura más cercana
  dentro de las permitidas.

**Trade-off:** cruce de regiones añade ~80-150 ms de latencia por operación
Blob ↔ Container App y un costo mínimo de egress. Despreciable para un
proyecto académico. En producción real se consolidarían en una sola región.

### 8.2 GitHub Container Registry (ghcr.io) en vez de Azure Container Registry

La misma política regional bloquea ACR en `mexicocentral`. Se evaluaron dos
caminos: crear ACR en otra región (añade latencia y complejidad) o usar
ghcr.io. Se eligió **ghcr.io** por:

- Está fuera del alcance de la política de Azure.
- Integración nativa con GitHub Actions vía `GITHUB_TOKEN` (sin credenciales
  adicionales).
- Gratis e ilimitado para repositorios públicos.
- Práctica común en industria desacoplar el registro del proveedor de cómputo.

### 8.3 Escala a cero (`min-replicas: 0`)

Los Container Apps se configuran con `min-replicas: 0`, lo que significa que
**bajan a cero réplicas cuando no hay tráfico** y no consumen crédito. Se
reactivan automáticamente al recibir una petición, con unos segundos de
arranque en frío (cold start). Esto es ideal para un proyecto académico donde
el endpoint solo se usa durante la sustentación.

### 8.4 Append Blob para registro de predicciones

El enunciado pide guardar las predicciones en archivos `.txt`. Una
implementación naive (leer el archivo, añadir línea, reescribir) tiene una
condición de carrera clásica: dos peticiones simultáneas pueden perder
predicciones. Se usa **Azure Append Blob**, que está diseñado específicamente
para append atómico desde múltiples productores. En producción real se
preferiría una tabla o cola, pero Append Blob es el compromiso correcto entre
cumplir el requisito y evitar la mala práctica.

### 8.5 Service Principal con scope limitado al Resource Group

El service principal `github-actions-mlops` se creó con rol `contributor`
**únicamente sobre el resource group** del proyecto, no sobre toda la
suscripción. Aplica el principio de menor privilegio: si la credencial se
filtrara, el daño máximo se limita a este resource group.

---

## 9. Limitaciones conocidas y mejoras futuras

- **Sin geo-replicación.** Single point of failure en cada región. Para
  producción, ACR Premium + Storage GRS.
- **Sin scanning de vulnerabilidades en las imágenes.** ghcr.io ofrece
  *Dependabot alerts*; en producción se evaluaría Trivy o Snyk en el pipeline.
- **Autenticación OIDC en vez de Service Principal con secret.** Más seguro
  porque no maneja credenciales de larga duración; se descartó por
  complejidad de configuración para un proyecto académico.
- **Sin canary deployment.** El despliegue es full replace; en producción se
  usaría tráfico dividido entre revisions de Container Apps.

---

## Licencia

Proyecto académico. Sin licencia comercial.
