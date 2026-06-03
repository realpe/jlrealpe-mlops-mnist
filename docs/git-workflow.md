# Flujo de trabajo con Git para este proyecto

> Guía práctica de los comandos Git que vas a usar durante el desarrollo del
> proyecto. Incluye flujo cotidiano, promoción dev → prod, recuperación de
> errores comunes y referencia rápida de comandos.

---

## 1. Modelo de ramas del proyecto

El proyecto tiene **tres ramas** que cumplen roles distintos:

| Rama   | Propósito                                              | Dispara pipeline |
|--------|--------------------------------------------------------|------------------|
| `main` | Rama base estable (snapshot del setup inicial)         | No              |
| `dev`  | Trabajo activo, experimentación, primeras pruebas      | Sí (workflow `dev.yml`) |
| `prod` | Solo recibe cambios ya validados en `dev`              | Sí (workflow `prod.yml`) |

**Regla de oro:** todo el trabajo cotidiano se hace en `dev`. La rama `prod`
solo recibe merges deliberados cuando algo está listo para "producción". A
`main` no se le toca durante el desarrollo activo del proyecto.

```
   main  ────────────────────────────────────●  (estado inicial, intocada)
                                              \
   dev   ────●───●───●───●───●───●───●───●─────●  (trabajo diario)
                          \                    \
   prod  ──────────────────●─────────────────────●  (promociones puntuales)
```

---

## 2. Flujo cotidiano (trabajar en `dev`)

Este es el ciclo que vas a repetir muchas veces durante el proyecto.

### 2.1 Asegurarte de estar en `dev`

```bash
git status                # ver en qué rama estás y si hay cambios pendientes
git checkout dev          # cambiar a dev si no estás ahí
```

### 2.2 Bajar lo último de GitHub (si trabajas desde otra máquina o tras varios días)

```bash
git pull
```

> Si solo trabajas desde tu Mac y el repo no tiene colaboradores, `git pull`
> casi siempre dirá "Already up to date". Es buena práctica ejecutarlo igual
> antes de empezar a trabajar.

### 2.3 Hacer tus cambios

Abre tu editor (VS Code, lo que uses), modifica los archivos que necesites.
Mientras editas, en cualquier momento puedes preguntarle a Git qué cambió:

```bash
git status                # qué archivos modificaste/agregaste/borraste
git diff                  # ver línea por línea qué cambió en cada archivo
git diff app/main.py      # ver cambios solo de un archivo específico
```

### 2.4 Stagear (preparar) los cambios

```bash
git add .                 # stagear TODOS los cambios del directorio actual
git add app/main.py       # stagear solo un archivo específico
git add app/              # stagear solo lo que está bajo una carpeta
```

> `git add` no sube nada todavía — solo marca qué cambios quieres incluir en
> el próximo commit. Permite hacer commits más quirúrgicos cuando tienes
> varios cambios mezclados.

### 2.5 Commit (guardar el snapshot)

```bash
git commit -m "Implementar endpoint /predict con preprocesamiento"
```

**Buenas prácticas para mensajes de commit:**

- Empezar con un verbo en infinitivo o imperativo: "Agregar", "Corregir",
  "Implementar", "Refactorizar".
- Una línea de resumen, idealmente <72 caracteres.
- Si el cambio es complejo, dejar línea en blanco y agregar descripción larga:

```bash
git commit -m "Agregar quality gate por accuracy en pipeline" -m "Si el modelo cae por debajo del umbral 0.90 en el test de regresión, el pipeline falla y no se despliega. Esto evita promover modelos degradados a prod."
```

### 2.6 Push (subir a GitHub)

```bash
git push
```

> Sin argumentos porque la rama ya quedó "tracked" cuando hiciste el primer
> `git push -u origin dev`. Git ya sabe a qué remote y rama subir.

**Importante:** este `git push` a la rama `dev` **dispara automáticamente el
workflow `.github/workflows/dev.yml`** (cuando esté implementado). En la
pestaña "Actions" de GitHub vas a ver el pipeline corriendo.

---

## 3. Promoción de `dev` a `prod`

Cuando algo en `dev` ya está probado, funcionando, y querés que pase a
producción (es decir, que se despliegue al endpoint de prod), hacés un
**merge** de `dev` hacia `prod`.

### 3.1 Verificar que todo está limpio en `dev`

```bash
git checkout dev
git status                # debe decir "nothing to commit, working tree clean"
git push                  # asegurarte de que dev está sincronizado con GitHub
```

### 3.2 Cambiar a `prod` y mergear

```bash
git checkout prod         # ir a la rama prod
git pull                  # asegurarte de tener la última versión de prod en GitHub
git merge dev             # traer todo el trabajo de dev hacia prod
```

**Si no hay conflictos** (lo normal cuando solo tú trabajas), Git hace un
"fast-forward merge" automático. Te muestra qué archivos cambiaron.

### 3.3 Empujar `prod` a GitHub

```bash
git push
```

Este push **dispara el workflow `.github/workflows/prod.yml`**, que correrá
los tests con umbral más estricto y, si pasan, desplegará al endpoint de prod.

### 3.4 Volver a `dev` para seguir trabajando

```bash
git checkout dev
```

> **Regla práctica:** termina cada sesión de trabajo con `git checkout dev`,
> así la próxima vez que abrás el proyecto ya estás listo para escribir
> código sin riesgo de tocar `prod` por accidente.

---

## 4. Casos comunes que te pueden aparecer

### 4.1 "Quiero deshacer cambios que NO he commiteado todavía"

Editaste algo, no te gustó, querés volver al estado del último commit.

```bash
# Descartar cambios en un archivo específico
git checkout -- app/main.py

# Descartar TODOS los cambios no commiteados (¡cuidado!)
git checkout -- .
```

### 4.2 "Hice `git add` pero todavía no commiteé y quiero des-stagear"

```bash
git restore --staged app/main.py    # quita el archivo del stage
                                     # los cambios siguen en el archivo
```

### 4.3 "Commiteé pero todavía no hice push, y me equivoqué"

**Opción A — solo cambiar el mensaje del último commit:**

```bash
git commit --amend -m "Mensaje corregido"
```

**Opción B — deshacer el último commit, mantener los cambios en el working tree:**

```bash
git reset --soft HEAD~1
# ahora los archivos están como estaban antes del commit, podés editar y volver a commitear
```

**Opción C — deshacer commit Y borrar los cambios (¡destructivo!):**

```bash
git reset --hard HEAD~1
# usa esto solo si estás seguro de que querés perder los cambios
```

### 4.4 "Ya hice push y quiero revertir"

⚠️ **Cuidado**: una vez en GitHub, no podés "borrar" historia sin afectar a
quien haya hecho `pull`. La forma limpia es crear un **commit de reversión**:

```bash
git revert HEAD               # crea un nuevo commit que deshace el anterior
git push
```

### 4.5 "Cambié de rama sin commitear y Git no me deja"

Git protege tu trabajo: si tenés cambios sin commitear, no te deja cambiar
de rama si ese cambio entra en conflicto con la rama destino.

**Opción rápida — guardar los cambios temporalmente con `stash`:**

```bash
git stash                 # guarda los cambios en un "estante" y limpia el working tree
git checkout otra-rama
# ... hacer lo que sea ...
git checkout dev
git stash pop             # recupera los cambios del estante
```

### 4.6 "Subí algo sensible (un .env, una clave) por error"

🚨 Acción inmediata: **considerar la credencial como comprometida y rotarla**
(borrar y regenerar en Azure / GitHub). Después, limpiar el repo:

```bash
# 1. Quitar el archivo del seguimiento de git pero dejarlo localmente
git rm --cached .env
echo ".env" >> .gitignore
git commit -m "Quitar .env del seguimiento"
git push
```

> El archivo seguirá apareciendo en el historial pasado del repo. Para
> borrarlo completamente del historial existe `git filter-repo`, pero requiere
> cuidado. Para este proyecto, lo más seguro y rápido es **rotar la credencial**
> (cualquiera que haya visto el commit ya tiene el valor).

### 4.7 "Quiero ver el historial de commits"

```bash
git log --oneline                       # vista compacta, un commit por línea
git log --oneline --graph --all         # con grafo de ramas, todas las ramas
git log --oneline -10                   # solo los últimos 10 commits
```

---

## 5. Commits típicos durante este proyecto

Para que tengas idea de cómo van a ser los commits durante el desarrollo,
estos son los hitos esperados:

```
Implementar funciones puras en app/model_utils.py
Implementar API FastAPI con /health y /predict
Agregar registro de predicciones en Append Blob
Agregar pruebas unitarias del modelo (shape + accuracy)
Crear Dockerfile y fijar requirements.txt
Implementar workflow dev.yml (test + build + deploy)
Implementar workflow prod.yml con umbral estricto
Corregir descarga del modelo desde Blob en el pipeline
Actualizar README con URLs finales de los endpoints
```

Cada uno de esos commits = un `git add . && git commit -m "..."` en la
rama `dev`. Cuando un bloque grande está listo (por ejemplo "API completa
y probada"), se hace promoción a `prod`.

---

## 6. Referencia rápida de comandos

| Necesito... | Comando |
|---|---|
| Ver en qué rama estoy | `git branch` o `git status` |
| Cambiar de rama | `git checkout <rama>` |
| Crear y cambiar a nueva rama | `git checkout -b <rama>` |
| Ver qué archivos cambiaron | `git status` |
| Ver cambios línea por línea | `git diff` |
| Preparar cambios para commit | `git add <archivo>` o `git add .` |
| Commitear lo preparado | `git commit -m "mensaje"` |
| Subir a GitHub | `git push` |
| Bajar de GitHub | `git pull` |
| Ver historial | `git log --oneline` |
| Mergear otra rama | `git merge <rama-origen>` |
| Guardar temporal y limpiar | `git stash` |
| Recuperar lo guardado | `git stash pop` |
| Deshacer cambios no commiteados | `git checkout -- <archivo>` |
| Deshacer último commit (sin perder cambios) | `git reset --soft HEAD~1` |
| Revertir un commit ya pusheado | `git revert HEAD` |

---

## 7. Configuración recomendada de Git (una vez por máquina)

Si todavía no la hiciste, conviene configurar tu identidad y algunos
comportamientos útiles:

```bash
git config --global user.name "José Luis Realpe Manrique"
git config --global user.email "94474911@u.icesi.edu.co"

# Que el editor por defecto sea VS Code (si lo usas)
git config --global core.editor "code --wait"

# Pull con rebase por defecto (historial más limpio)
git config --global pull.rebase false

# Mostrar ramas con colores
git config --global color.ui auto

# Que git push solo suba la rama actual (más seguro)
git config --global push.default current
```

Verifica con: `git config --global --list`
