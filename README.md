# Blender Lab 🧪

Laboratorio privado para ejecutar Blender en Ubuntu mediante GitHub Actions, sin instalar Blender en el móvil.

## Qué hace

- Ejecuta Blender en modo headless (sin interfaz gráfica).
- Genera una escena de prueba mediante Python.
- Renderiza una imagen PNG.
- Publica el archivo editable `.blend`, el render y el registro como artefactos de la ejecución.
- Se ejecuta al cambiar archivos del laboratorio o manualmente desde **Actions → Blender Headless Lab → Run workflow**.

## Estructura

- `scripts/create_scene.py`: crea la escena y el render.
- `.github/workflows/blender.yml`: instala Blender y ejecuta el script en Ubuntu.
- `artifacts/`: salida de la ejecución, subida como artefacto de GitHub Actions.

## Cómo recuperar resultados

Abre la pestaña **Actions**, entra en la ejecución más reciente y descarga `blender-lab-output` en la sección **Artifacts**.

## Límites

Este laboratorio ofrece ejecuciones remotas reproducibles, no una terminal persistente ni una sesión interactiva de Blender. Los artefactos de Actions tienen una retención limitada.
