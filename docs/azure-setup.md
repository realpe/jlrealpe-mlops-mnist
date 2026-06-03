# Guía de configuración de Azure

Guía paso a paso para aprovisionar la infraestructura en Azure y conectar el
repositorio con GitHub Actions. Todos los comandos usan **Azure CLI** (`az`)
para que el proceso sea reproducible y fácil de explicar en la sustentación.

> **Antes de empezar:** instala Azure CLI y autentícate.
> ```bash
> az login                          # abre el navegador para iniciar sesión
> az account show                   # confirma la suscripción activa
> ```
> Si tienes varias suscripciones, fija la de estudiante:
> ```bash
> az account set --subscription "Azure for Students"
> ```

---

## 0. Variables de trabajo (defínelas una vez en tu terminal)

> **Nota sobre las regiones elegidas (multi-región):**
> Este proyecto usa **dos regiones distintas** debido a restricciones de la
> suscripción de Azure for Students:
>
> - **Storage Account → `mexicocentral`** (la región más cercana a Colombia,
>   minimiza latencia para subir/descargar el modelo y los datos).
> - **Container Apps Environment + Container Apps → `eastus2`** (Mexico Central
>   no soporta aún el servicio Container Apps; East US 2 sí, está permitida por
>   la política, y es región madura con cobertura completa).
>
> **Por qué multi-región:** Azure for Students aplica una política llamada
> *"Allowed resource deployment regions"* que restringe la creación de recursos
> a un subconjunto de regiones (en esta suscripción: `southcentralus`,
> `northcentralus`, `chilecentral`, `mexicocentral`, `eastus2`). De esas,
> Container Apps solo opera en `southcentralus`, `northcentralus` y `eastus2`.
> Se eligió `eastus2` por ser la más madura y completa de Azure.
>
> **Implicación técnica:** las Container Apps (en US) accederán al Storage
> (en MX) cruzando regiones, lo que añade ~80-150 ms de latencia por operación
> y un costo mínimo de egress. Para este proyecto académico el impacto es
> despreciable. En producción real se consolidarían en una sola región una vez
> Container Apps esté disponible en Mexico Central.
>
> Si reproduces este setup en otra suscripción, verifica primero tus regiones
> permitidas en: *Portal → Policy → Authoring → Assignments → "Allowed resource
> deployment regions" → Parameters*.
>
> **Nota sobre ACR:** durante el setup se descubrió que Azure Container
> Registry tampoco está disponible en `mexicocentral` para esta cuenta. Por eso
> el proyecto usa **GitHub Container Registry (ghcr.io)** en lugar de ACR —
> ver paso 4 para el detalle.

Definir variables al inicio evita errores de tipeo y hace los comandos
reutilizables. El nombre de Storage ya incluye el identificador `joserealpe`
para que sea único a nivel global en Azure.

```bash
# --- Identificación ---
export RG="rg-proyecto-mlops"               # resource group (agrupa todo)
export LOCATION="mexicocentral"             # región del Storage (más cercana a Colombia)
export LOCATION_COMPUTE="eastus2"           # región del cómputo (Container Apps no
                                             # está disponible en mexicocentral)

# --- Storage (nombres SOLO minúsculas y números, sin guiones, 3-24 chars) ---
export STORAGE="stmlopsjoserealpe"

# --- Container Apps ---
export ACA_ENV="env-mlops"                  # entorno de Container Apps
export APP_DEV="mnist-api-dev"              # app del endpoint dev
export APP_PROD="mnist-api-prod"            # app del endpoint prod
```

> **Nota:** estas variables viven solo en tu sesión de terminal. Si cierras la
> terminal, vuelve a exportarlas. No las subas al repo.

---

## 1. Resource Group

El resource group es un contenedor lógico que agrupa todos los recursos del
proyecto. Borrarlo al final elimina TODO de un solo comando (útil para limpiar).

```bash
az group create --name "$RG" --location "$LOCATION"
```

---

## 2. Storage Account + contenedores (los "buckets")

Aquí viven el modelo `.onnx`, los datos de prueba y los archivos de
predicciones. Creamos la cuenta y luego tres contenedores separados por
responsabilidad.

```bash
# Crear la Storage Account (SKU Standard_LRS = el más barato, redundancia local)
az storage account create \
  --name "$STORAGE" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2

# Obtener la connection string y guardarla en una variable
# (la usaremos para crear los contenedores y luego como SECRET en GitHub)
export AZURE_STORAGE_CONNECTION_STRING=$(az storage account show-connection-string \
  --name "$STORAGE" \
  --resource-group "$RG" \
  --query connectionString --output tsv)

# Crear los tres contenedores
az storage container create --name "models"      --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
az storage container create --name "data"        --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
az storage container create --name "predictions" --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
```

> **SEGURIDAD:** la `AZURE_STORAGE_CONNECTION_STRING` es una credencial con
> acceso total a tu storage. NUNCA la subas al repo, NO la pegues en chats ni
> logs. Solo va en tu `.env` local (ignorado por git) y en GitHub Secrets.

> **Decisión técnica:** `Standard_LRS` (Locally Redundant Storage) es el tier
> más económico; replica los datos dentro de un solo datacenter. Para un
> proyecto académico es suficiente. La alternativa `Standard_GRS` replica entre
> regiones (más caro, innecesario aquí).

---

## 3. Subir el modelo y los datos al Blob

El modelo `.onnx` NO va en el repo (lo prohíbe el enunciado). Lo subes una vez
desde tu máquina al contenedor `models`.

> ⚠️ **Atención:** el modelo MNIST en el repo oficial `onnx/models` está
> almacenado con **Git LFS** (Large File Storage). Una `curl` directa a
> `raw.githubusercontent.com/...` solo descarga el *pointer* de LFS (~130
> bytes de texto), no el binario real. Hay que descargarlo de forma especial:

**Opción A — desde el navegador (recomendada, lo más simple):**

1. Abrir en navegador: `https://github.com/onnx/models/blob/main/validated/vision/classification/mnist/model/mnist-12.onnx`
2. Click en el icono **"Download raw file"** (arriba a la derecha del visor).
3. Guardar el archivo como `mnist-12.onnx` en el directorio del proyecto.
4. Verificar el tamaño: el archivo real pesa ~26 KB. Si pesa <1 KB, no se
   descargó correctamente.

**Opción B — desde la terminal con git-lfs:**

```bash
brew install git-lfs && git lfs install   # instalar una vez en tu Mac
mkdir -p /tmp/onnx-mnist && cd /tmp/onnx-mnist
git clone --depth 1 --filter=blob:none --sparse https://github.com/onnx/models.git
cd models
git sparse-checkout set validated/vision/classification/mnist/model
git lfs pull --include "validated/vision/classification/mnist/model/mnist-12.onnx"
cp validated/vision/classification/mnist/model/mnist-12.onnx ~/<ruta-a-tu-proyecto>/
```

**Una vez tengas el archivo descargado, súbelo al Blob:**

```bash
az storage blob upload \
  --container-name "models" \
  --name "mnist-12.onnx" \
  --file "mnist-12.onnx" \
  --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
```

> Los **datos de prueba** los subiremos con el script `scripts/upload_to_blob.py`
> en el siguiente paso del proyecto (cuando definamos en qué formato los
> guardamos). Por ahora basta con el modelo.

---

## 4. Container Registry — decisión: GitHub Container Registry (ghcr.io)

> **Por qué NO usamos Azure Container Registry (ACR):**
> Durante el setup, la política *Allowed resource deployment regions* de Azure
> for Students bloqueó la creación de ACR en `mexicocentral` (la única región
> donde el Storage Account funciona en esta suscripción). Crear ACR en otra
> región habría sido viable pero añade latencia y complejidad operacional.

**Decisión:** usar **GitHub Container Registry (ghcr.io)** como registro de
imágenes Docker. ghcr.io vive en GitHub, no en Azure, así que queda fuera del
alcance de la política de regiones. Adicionalmente:

- Está integrado nativamente con GitHub Actions: el `GITHUB_TOKEN` automático
  del workflow autentica el `docker push` sin configurar credenciales extra.
- Es **gratuito** para repositorios públicos y tiene un tier gratuito generoso
  para privados.
- Es práctica común en industria desacoplar el registro de imágenes del
  proveedor de cómputo (registro en un proveedor, despliegue en otro).
- Reduce la cantidad de recursos Azure a aprovisionar y monitorear.

**Trade-off honesto:** en un escenario productivo "puro Azure" se preferiría
ACR por integración nativa con Entra ID, geo-replicación y scanning de
vulnerabilidades. Para este proyecto académico ninguna de esas features aplica.

**No hay comandos `az` que ejecutar en este paso.** La configuración de
ghcr.io vivirá en el workflow de GitHub Actions (paso del proyecto siguiente)
y en una credencial de registro que se añadirá a las Container Apps en el
paso 6.

---

## 5. Entorno de Container Apps

Antes de crear las apps, se crea el "environment" que las aloja. Crearlo
explícitamente (en vez de dejar que `az containerapp up` lo cree solo) hace el
despliegue posterior más rápido y predecible.

```bash
# Registrar el proveedor (solo la primera vez en la suscripción)
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights

# Instalar/actualizar la extensión de containerapp
az extension add --name containerapp --upgrade

# Crear el entorno (en la región de cómputo, NO la del storage)
az containerapp env create \
  --name "$ACA_ENV" \
  --resource-group "$RG" \
  --location "$LOCATION_COMPUTE"
```

---

## 6. Crear las dos Container Apps (endpoints dev y prod)

Creamos dos apps con una imagen "hello-world" temporal solo para que existan y
tengan URL. El pipeline luego reemplaza esa imagen por la real. Cada app es un
endpoint independiente (la opción más simple: una rama = una app).

```bash
# App DEV
az containerapp create \
  --name "$APP_DEV" \
  --resource-group "$RG" \
  --environment "$ACA_ENV" \
  --image "mcr.microsoft.com/k8se/quickstart:latest" \
  --target-port 80 \
  --ingress external \
  --min-replicas 0 \
  --max-replicas 2

# App PROD
az containerapp create \
  --name "$APP_PROD" \
  --resource-group "$RG" \
  --environment "$ACA_ENV" \
  --image "mcr.microsoft.com/k8se/quickstart:latest" \
  --target-port 80 \
  --ingress external \
  --min-replicas 0 \
  --max-replicas 2
```

> **CLAVE — escala a cero:** `--min-replicas 0` es lo que hace que la app baje a
> CERO réplicas cuando no hay tráfico, y por tanto **no consuma crédito** estando
> inactiva. No tienes que "apagar" nada manualmente. Se reactiva sola cuando
> llega una petición (con unos segundos de arranque en frío, normal).

Obtén las URLs de los endpoints (las necesitarás para el README y la demo):

```bash
az containerapp show --name "$APP_DEV"  --resource-group "$RG" \
  --query properties.configuration.ingress.fqdn --output tsv
az containerapp show --name "$APP_PROD" --resource-group "$RG" \
  --query properties.configuration.ingress.fqdn --output tsv
```

---

## 7. Service Principal (para que GitHub Actions despliegue en Azure)

GitHub Actions necesita autenticarse en Azure. Creamos un "service principal":
una identidad-robot con permisos limitados al resource group del proyecto.

```bash
# Obtener el ID de la suscripción
export SUB_ID=$(az account show --query id --output tsv)

# Crear el service principal con permisos SOLO sobre nuestro resource group
az ad sp create-for-rbac \
  --name "github-actions-mlops" \
  --role contributor \
  --scopes "/subscriptions/$SUB_ID/resourceGroups/$RG" \
  --sdk-auth
```

El comando imprime un **JSON** con `clientId`, `clientSecret`, `subscriptionId`
y `tenantId`. **Copia TODO ese JSON** — es el valor del secret `AZURE_CREDENTIALS`.

> **SEGURIDAD CRÍTICA:** ese JSON es una llave de acceso a tu Azure. Cópialo
> directo a GitHub Secrets (paso 8). NO lo guardes en archivos del repo, NO lo
> pegues en chats, NO lo dejes en el historial de la terminal más de lo
> necesario. Si se filtra, regéneralo de inmediato borrando el SP:
> `az ad sp delete --id <clientId>`.

> **Scope acotado (buena práctica):** damos permiso `contributor` SOLO sobre
> `$RG`, no sobre toda la suscripción. Si la credencial se filtrara, el daño se
> limita a este resource group. Es el principio de menor privilegio.

> **Alternativa de producción (OIDC):** en vez de un secreto de larga duración,
> se pueden usar *federated credentials* (OIDC), donde GitHub se autentica con
> Azure sin almacenar contraseñas. Es más seguro pero más complejo de
> configurar. Para este proyecto el service principal con secreto es suficiente;
> menciona OIDC si te preguntan por hardening en la sustentación.

---

## 8. Registrar los GitHub Secrets

En tu repo de GitHub: **Settings > Secrets and variables > Actions >
New repository secret**. Crea estos secrets:

| Nombre del secret                 | Valor                                              |
|-----------------------------------|----------------------------------------------------|
| `AZURE_CREDENTIALS`               | El JSON completo del paso 7                         |
| `AZURE_STORAGE_CONNECTION_STRING` | La connection string del paso 2                    |
| `RESOURCE_GROUP`                  | `rg-proyecto-mlops`                                |

> El `GITHUB_TOKEN` que usaremos para autenticarnos contra ghcr.io NO se
> registra como secret: GitHub Actions lo provee automáticamente a cada
> workflow run, así que no hay que crearlo manualmente.

> **Nunca** escribas estos valores en los archivos `.yml`. En el workflow se
> referencian como `${{ secrets.NOMBRE }}`, así GitHub los inyecta sin
> exponerlos en los logs.

---

## 9. Budget con alerta (control de gasto)

Aunque Azure for Students no cobra a una tarjeta, conviene una alerta temprana
para no agotar el crédito por accidente (ej: una app mal configurada que no
escala a cero).

En el portal: **Cost Management > Budgets > + Add**. Define un monto (ej: 20 USD
mensual) y alertas por email al 50% y 80%. El budget NOTIFICA, no corta el
gasto automáticamente — es una alarma temprana, no un fusible.

---

## 10. Verificación final

Antes de pasar al código, confirma que todo existe:

```bash
az resource list --resource-group "$RG" --output table
```

Deberías ver: la Storage Account, el Container Apps Environment y las dos
Container Apps.

---

## Limpieza (al terminar el proyecto)

Para borrar TODO y dejar de consumir cualquier recurso:

```bash
az group delete --name "$RG" --yes --no-wait
```

> Esto elimina el resource group completo. Como el modelo y la config se
> reconstruyen con un `git push` (gracias al pipeline), puedes borrar todo
> después de la sustentación y recrearlo cuando quieras. Ese es justamente el
> valor de tener un despliegue automatizado.
