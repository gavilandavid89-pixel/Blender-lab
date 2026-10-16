# ST-LAT Engine — matriz de pruebas

**Última actualización:** 2026-10-16  
**Regla:** una capacidad se marca como implementada solo si existe código ejecutable y una prueba reproducible. Una especificación o un archivo de ejemplo, por sí solos, no prueban que el motor aplique esa regla en tiempo de ejecución.

## 1. Ejecutar las pruebas

Desde la raíz del repositorio:

```bash
python3 scripts/validate_scene_profiles.py
python3 scripts/validate_world_manifest.py --self-test
python3 scripts/validate_motion_report.py --self-test
python3 scripts/validate_camera_isolation_report.py --self-test
python3 scripts/validate_deterministic_manifest.py --self-test
python3 -m unittest discover -s tests -v
```

La acción **Blender Headless Lab** ejecuta las comprobaciones rápidas antes de instalar Blender; después construye la escena, valida movimiento y manifiesto, compara IDs, transforms y hashes de malla entre dos builds independientes, prueba el aislamiento de cámara sobre la escena guardada y publica el artefacto `stlat-world3d-output`.

Ejecución de CI verificada: [run 38830444349](https://github.com/gavilandavid89-pixel/Blender-lab/actions/runs/38830444349) — **success**. Esta ejecución validó los perfiles, el autodiagnóstico del manifiesto, la construcción/render, la validación de movimiento, el manifiesto generado y los artefactos. La suite de regresión general y el validador independiente de movimiento pasaron en [CI run 38831099483](https://github.com/gavilandavid89-pixel/Blender-lab/actions/runs/38831099483). Los nuevos contratos de estado versionado descritos a continuación requieren su propia ejecución verde.

La ejecución completa más reciente verificada es [run 38966075154](https://github.com/gavilandavid89-pixel/Blender-lab/actions/runs/38966075154) — **success**, incluida la comparación determinista y la prueba de aislamiento de cámara.

## 2. Matriz actual

| ID | Riesgo / contrato | Prueba automatizada actual | Evidencia | Límite conocido |
|---|---|---|---|---|
| T-001 | Perfil neutro incompleto o incompatible | `scripts/validate_scene_profiles.py` | Salida `SCENE_PROFILE_VALIDATION=PASS` | Valida reglas explícitas seleccionadas; no interpreta prompts ni ejecuta el selector M14 |
| T-002 | Manifiesto con esquema, unidades o ejes incorrectos | `scripts/validate_world_manifest.py` | `stlat-world3d-manifest.json` | Valida el contrato `stlat.world3d.v1`, no una base de datos persistente |
| T-003 | ID de entidad duplicado | Autoprueba del validador + regresión T-014 | Mensaje `duplicate entity id` | Los IDs se comprueban dentro de un manifiesto; aún no entre versiones/proyectos |
| T-004 | AABB invertida, vector no finito o dimensión negativa | Autoprueba + regresiones T-011–T-015 | Errores semánticos por campo | AABB es una aproximación de caja delimitadora |
| T-005 | Rol semántico requerido ausente | Validador del manifiesto | `required semantic roles missing` | Lista de roles mínimos específica de la escena de prueba |
| T-006 | Pose inicial inválida | `scripts/world3d_validate_motion.py` | `initial_pose_is_valid` en informe de movimiento | La pose se prueba con mallas proxy y AABB |
| T-007 | Ruta segura con colisión o fuera de límites | Muestreo de 49 posiciones | `safe_path_is_collision_free` | El muestreo discreto no garantiza ausencia de colisión entre muestras |
| T-008 | Ruta bloqueada atraviesa la cama | Ruta deliberada hacia la cama + filtro por geometría `Bed.*` | `bed_path_hits_bed_geometry` y `bed_geometry_collision_hits` | Solo se comprueba esta ruta y el conjunto actual de obstáculos |
| T-009 | Detector no detecta salida del cuarto | Posición deliberadamente fuera de límites | `room_boundary_violation_detected` y partes fuera | No valida navegación global |
| T-010 | Render o escena faltante | Paso `Validate output files` del workflow | Blender, PNG principal, PNG cenital y dos JSON | No evalúa calidad artística ni fidelidad de vídeo |
| T-011 | Coordenadas NaN/Infinity | `tests/test_contracts.py` | Prueba unitaria negativa | Se valida el manifiesto serializado; no todos los cálculos internos de Blender |
| T-012 | Booleanos aceptados como números | `tests/test_contracts.py` | Prueba unitaria negativa | Aplica a vectores validados por el manifiesto |
| T-013 | Dimensiones negativas | `tests/test_contracts.py` | Prueba unitaria negativa | No inspecciona la topología de la malla |
| T-014 | IDs duplicados | `tests/test_contracts.py` | Prueba unitaria negativa | Alcance local a un manifiesto |
| T-015 | Cantidad de objetos no coincide | `tests/test_contracts.py` | Prueba unitaria negativa | No garantiza identidad entre ejecuciones |
| T-016 | El ejemplo de perfil viola su contrato | Subproceso de `validate_scene_profiles.py` desde unittest | Prueba de integración ligera | No valida todo el vocabulario JSON Schema genérico |
| T-017 | Salida con informe de movimiento fallido | El script de movimiento lanza excepción si un check falla | Código de salida no cero en CI | El script que genera la evidencia y el validador son controles separados |
| T-018 | Informe persistido incompleto o evidencia contradictoria | `scripts/validate_motion_report.py` + autoprueba negativa | `MOTION_REPORT_VALIDATION=PASS` | Valida la evidencia estructurada; no reejecuta la física ni certifica el mundo real |
| T-019 | Snapshot de mundo con campos, ejes o geometría inválidos | `scripts/world_state_contract.py` + `tests/test_world_state_contract.py` | Errores por campo y regresiones negativas | Valida invariantes esenciales, no todo el estándar JSON Schema |
| T-020 | Identidad o firma de apariencia cambia sin aprobación | `validate_transition` + pruebas positivas/negativas | Rechazo de cambios protegidos no aprobados | No analiza imágenes ni determina identidad visual real |
| T-021 | Salto de versión o parent_version incorrecto | `validate_transition` | Linaje de versiones | No guarda snapshots en una base de datos |
| T-022 | Cambio de cámara muta entidades del mundo | `validate_camera_isolation` | Rechaza cualquier diferencia en entidades no cámara | Prueba estados JSON; todavía no intercepta cambios dentro de Blender |
| T-023 | Entidad aparece/desaparece sin evento aprobado | `validate_transition` | Pruebas de ciclo de vida de entidades | Los eventos son datos declarados; la autorización externa aún no está conectada |
| T-024 | IDs o transformaciones cambian entre dos builds idénticos | `scripts/validate_deterministic_manifest.py` + segunda construcción Blender sin render | `stlat-world3d-determinism.json` | Comprueba metadatos semánticos y espaciales exportados |
| T-025 | Geometría cambia manteniendo ID y límites similares | Hash SHA-256 canonizado de vértices, aristas y caras evaluados | `mesh_geometry_sha256` y `stlat-world3d-determinism.json` | No compara materiales, texturas, rig/animación ni píxeles de render |
| T-026 | Replay de transformaciones, creación/eliminación, rol e identidad; rechazar eventos no aprobados o contradictorios | `scripts/world_state_replay.py` + `tests/test_world_state_contract.py` | `artifacts/stlat-world-state-replay.json` y pruebas unitarias | Replay en memoria; no es autorización criptográfica ni persistencia de base de datos |

## 3. Capacidades aún no verificadas / no implementadas

| ID futuro | Prueba que debe existir antes de integrar un generador de vídeo | Estado |
|---|---|---|
| F-001 | Cambiar cámara y demostrar que ninguna transformación canónica del mundo cambia | Parcial: prueba real de Blender integrada en CI; falta una capa de permisos/API que impida mutaciones externas |
| F-002 | Repetir una petición y conservar IDs de identidad, malla y entidad entre versiones | Parcial: builds deterministas conservan IDs y transforms; no existe todavía registro persistente de assets/identidades entre cambios intencionales |
| F-003 | Aplicar una orden explícita que contradice un default y demostrar que gana la orden, registrando el conflicto | Pendiente; contrato documentado, motor M15 no implementado |
| F-004 | Prompt sin muebles/armas/vehículos: comprobar que no aparecen entidades implícitas | Pendiente; el perfil declara prohibiciones, no hay compilador de prompt integrado |
| F-005 | Restaurar snapshot y reproducir eventos hasta obtener estado equivalente | Parcial: replay determinista en memoria para creación/eliminación/transformación/rol/identidad con evidencia JSON; falta persistencia, relaciones y reconciliación con Blender |
| F-006 | Misma identidad en varias cámaras/tiempos sin cambiar proporciones ni ID | Pendiente; el personaje actual es proxy |
| F-007 | Colisiones con cápsulas o volúmenes continuos y prueba de movimiento rápido | Pendiente; el validador actual usa AABB muestreada |
| F-008 | Detectar cambio no autorizado de ropa, apariencia, posición o número de sujetos en vídeo | Pendiente; no hay evaluador temporal conectado |
| F-009 | Registrar origen y confianza de cada valor: explícito, aprobado, default, inferido o desconocido | Pendiente; ledger M15 no implementado |
| F-010 | Reparación limitada que nunca relaje restricciones superiores para “pasar” | Pendiente; M11 es diseño |
| F-011 | Repetición limpia de CI con todos los tests rápidos y Blender en verde | Verificado en [run 38964496099](https://github.com/gavilandavid89-pixel/Blender-lab/actions/runs/38964496099) |


## 4. Criterio de aprobación

- **Verde local**: todos los comandos rápidos terminan con código cero.
- **Verde CI**: el workflow completo termina en `success`, incluidos los pasos de Blender y publicación de artefactos.
- **Capacidad demostrada**: existe prueba positiva y al menos una prueba negativa pertinente, con evidencia guardada.
- **No verificado**: existe una salida, pero falta evidencia para una afirmación central.
- **No implementado**: hay un contrato o una idea, pero no hay código funcional y pruebas que la ejecuten.

Un resultado verde del laboratorio **no demuestra** que un generador de vídeo vaya a obedecer las referencias. Solo demuestra los contratos y pruebas enumerados en esta matriz.
