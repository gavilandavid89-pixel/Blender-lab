# ST-LAT World3D Lab 🧪

Laboratorio privado para probar el mundo 3D controlado de ST-LAT Engine desde Ubuntu remoto, sin necesitar un PC ni instalar Blender en el móvil.

## Objetivo

Construir una escena 3D reproducible que funcione como fuente de verdad espacial para un futuro sistema de generación de vídeo. La IA no debe poder mover objetos arbitrariamente, atravesar obstáculos ni cambiar la distribución del escenario sin que el sistema lo detecte.

## Qué genera

- `stlat-world3d.blend`: escena editable de Blender.
- `stlat-world3d-main.png`: referencia visual principal.
- `stlat-world3d-topdown.png`: referencia cenital.
- `stlat-world3d-manifest.json`: contrato del mundo, ejes, unidades, roles, transformaciones, AABB y validaciones estructurales.
- `stlat-world3d-motion-validation.json`: resultado de pruebas de recorrido seguro, colisión deliberada con la cama y salida deliberada de los límites.
- `blender.log`: registro de ejecución.

## Contrato espacial inicial

- Unidades: metros.
- Ejes: X = derecha, Y = profundidad (positivo hacia la pared del fondo), Z = arriba.
- Habitación interior: X/Y entre -4 y 4; Z entre 0 y 3.2.
- Cada objeto tiene un rol semántico y un identificador.
- El personaje es por ahora un proxy geométrico segmentado, no un rig ni una identidad final.

## Validación de movimiento

`scripts/world3d_validate_motion.py` abre la escena guardada y comprueba tres casos:

1. Un recorrido por el espacio libre debe terminar sin colisiones ni salirse de la habitación.
2. Un recorrido dirigido intencionalmente hacia la cama debe detectar el choque.
3. Una posición fuera de la habitación debe activar el detector de límites.

La validación usa muestras de trayectoria y cajas delimitadoras alineadas con los ejes (AABB). Es una prueba conservadora útil para detectar contradicciones espaciales; **no equivale todavía a una simulación física completa** y no valida deformación de mallas ni calidad de animación.

## Ejecución

Los cambios en `scripts/**`, este README o el workflow activan GitHub Actions. También se puede iniciar manualmente desde **Actions → Blender Headless Lab → Run workflow**.

El artefacto `stlat-world3d-output` contiene la escena, las imágenes y los informes.

## Lo que aún falta

- Colisiones de geometría más precisas y cuerpo del personaje como volumen coherente.
- Caminos con obstáculos y navegación de varias etapas.
- Rig/esqueleto, identidad del personaje y memoria entre tomas.
- Referencias por fotograma (profundidad, silueta, posición y cámara).
- Comparación automática de fotogramas generados contra el estado del mundo y detección de desviaciones.

No se considera implementada ninguna de estas capacidades hasta que tenga pruebas reproducibles.
