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

## Especificaciones de arquitectura

- [Arquitectura funcional y módulos M00–M13](docs/STLAT_ENGINE_SPEC.md)
- [Contratos operativos de módulos M00–M16](docs/SCENE_AND_MODULE_CONTRACTS.md)
- [Reglas de escenas neutras y valores por defecto](docs/NEUTRAL_SCENES.md)
- [Esquema JSON de perfiles de escena](docs/schemas/scene-profile.v1.schema.json)
- [Perfil de ejemplo neutral_studio](docs/examples/neutral-studio.v1.json)
- [Esquema del estado persistente del mundo](docs/schemas/world-state.v1.schema.json)
- [Matriz de pruebas, evidencia y capacidades pendientes](docs/TEST_MATRIX.md)
- [Contrato ejecutable de snapshots y continuidad de identidad](scripts/world_state_contract.py)
- [Guía de CI, artefactos y diagnóstico de fallos](docs/CI_AND_ARTIFACTS.md)

La documentación separa los contratos diseñados de las capacidades que ya tienen pruebas. Las escenas neutras son perfiles explícitos; no autorizan a inventar entidades narrativas.

## Pruebas de contrato

Desde la raíz del repositorio, las comprobaciones rápidas no necesitan Blender ni dependencias externas:

```bash
python3 scripts/validate_scene_profiles.py
python3 scripts/validate_world_manifest.py --self-test
python3 scripts/validate_motion_report.py --self-test
python3 -m unittest discover -s tests -v
# La suite incluye contratos de snapshots, continuidad de identidad y aislamiento de cámara
```

La acción de GitHub ejecuta estos controles antes de instalar Blender y después construye la escena, valida el informe persistido de movimiento y el manifiesto, y publica los artefactos. La [matriz de pruebas](docs/TEST_MATRIX.md) separa las comprobaciones reales de las capacidades aún pendientes; la [guía de CI y diagnóstico](docs/CI_AND_ARTIFACTS.md) explica cómo interpretar los informes y depurar fallos.

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
