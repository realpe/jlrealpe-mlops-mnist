# Sistema de Despliegue Automático de Modelos ONNX (MLOps)

> Proyecto final — Maestría en IA Aplicada, Universidad Icesi
> Despliegue automático de un modelo de clasificación de imágenes (MNIST, ONNX) mediante CI/CD con GitHub Actions sobre Azure Container Apps.

---

## 1. Descripción de la solución

Sistema de despliegue continuo que, ante cada `push` a las ramas `dev` o `prod`,
ejecuta automáticamente pruebas sobre un nuevo modelo y, si las supera, lo
despliega en un endpoint de Azure. El modelo se sirve a través de una API REST
construida con FastAPI.

*(Sección a completar: explicación más detallada del problema y la propuesta.)*

## 2. Arquitectura

*(Sección a completar: diagrama y descripción de componentes — GitHub Actions,
Azure Blob Storage, GitHub Container Registry, Azure Container Apps.)*

- **Modelo:** MNIST (clasificación de dígitos manuscritos) en formato ONNX.
- **Almacenamiento:** Azure Blob Storage (modelo, datos de prueba, predicciones).
- **Registro de imágenes:** GitHub Container Registry (ghcr.io).
- **Cómputo:** Azure Container Apps (escala a cero).
- **CI/CD:** GitHub Actions (un workflow por rama).

## 3. Estructura del repositorio

*(Sección a completar: árbol de carpetas y explicación de cada parte.)*

## 4. Flujo de CI/CD

*(Sección a completar: descripción de las etapas test y build/promote.)*

## 5. Endpoints

| Entorno | Rama   | URL del endpoint        |
|---------|--------|-------------------------|
| dev     | `dev`  | *(a completar)*         |
| prod    | `prod` | *(a completar)*         |

## 6. Cómo ejecutar localmente

*(Sección a completar: pasos para correr la API y las pruebas en local.)*

## 7. Configuración en Azure

*(Sección a completar: recursos a crear y secrets de GitHub necesarios.)*
