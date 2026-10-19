# ST-LAT Engine — matriz de pruebas

**Última actualización:** 2026-10-18  
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

La ejecución completa más reciente verificada antes de esta integración es [run 38970829039](https://github.com/gavilandavid89-pixel/Blender-lab/actions/runs/38970829039) — **success**, incluida la comparación determinista y la prueba de aislamiento de cámara.

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
| T-027 | Entidad física cruza los límites duros del mundo por su AABB o por el origen de transformación | `validate_state` + regresiones positivas/negativas y replay | Errores `bounds exceed hard world bounds` y `transform.position exceeds hard world bounds` | Cámaras excluidas explícitamente porque pueden estar fuera del volumen físico |
| T-028 | Snapshot alterado, versión inmutable, hueco de historial o salto de linaje | `scripts/world_state_store.py` + regresiones de almacenamiento | `artifacts/stlat-world-state-store.json` y pruebas unitarias | Almacén local de un solo escritor; SHA-256 no es firma criptográfica |
| T-029 | Jerarquía de entidades con padre inexistente, autorreferencia o ciclo | `validate_state` + regresiones de jerarquía | Errores de referencia y ciclo de padre | Valida el grafo estructural; no calcula transformaciones heredadas de Blender |
| T-030 | Reparentado silencioso o evento de reparentado contradictorio | `validate_transition` + `entity_parent_change_approved` en replay | Pruebas de aprobación, parent anterior/nuevo y ciclo | No recalcula transforms heredadas por jerarquía |
| T-031 | Replay tras recarga reconstruye exactamente la versión persistida | `WorldStateStore` + `replay_events` + hashes canónicos | `replay_after_reload_matches_persisted_version` y `replayed_state_sha256` en informe de almacén | La integración CI cubre un evento de transformación; no simula un servicio multiusuario ni sincroniza Blender |
| T-032 | Replay de varios eventos encadenados conserva versiones intermedias y rechaza una secuencia contradictoria sin mutar el snapshot de entrada | `WorldEventReplayTests`: transformación → reparentado → cambio de identidad; prueba negativa de timestamp regresivo | Suite `python3 -m unittest discover -s tests -v` en CI | Replay en memoria; todavía no sincroniza el estado con Blender ni aporta autorización criptográfica |
| T-033 | Replay de varios eventos tras recargar snapshots conserva movimiento, jerarquía e identidad entre cuatro versiones | `scripts/validate_world_store.py` persiste v1–v4, recarga todas y compara replay canónico con la última versión | `multi_event_chain_replay_matches_persisted_latest` y checks de linaje/identidad en `stlat-world-state-store.json` | Secuencia de prueba acotada; el almacén sigue siendo local y de un solo escritor |
| T-034 | Aplicar un snapshot validado a Blender no altera entidades no solicitadas y revierte una operación inválida | `scripts/world3d_sync_state.py` sobre la escena guardada: preflight de IDs/roles, aplicación de transform, lectura de vuelta de transform y AABB evaluada, invariancia de objetos no objetivo, rechazo de rol incorrecto y rollback de bounds incorrectos | `artifacts/stlat-world-state-blender-sync.json` | Solo mallas existentes sin padre; no crea/elimina/reparenta objetos, no sincroniza cámara/luces/animación y no guarda automáticamente |
| T-035 | El estado recuperado desde persistencia, tras replay de un evento aprobado, se refleja correctamente en la escena Blender | Autoprueba integrada de `scripts/world3d_sync_state.py`: genera v1, reproduce un evento aprobado, guarda v1/v2, recarga el último snapshot, compara replay canónico y aplica v2 a Blender | `persisted_replay_matches_latest` y `persisted_replay_applied_to_blender` en `artifacts/stlat-world-state-blender-sync.json` | Prueba de una entidad/movimiento; todavía no es una restauración completa de toda la escena ni un servicio continuo de sincronización |
| T-036 | Un movimiento sólido no puede atravesar un obstáculo aunque su pose final esté libre | Autoprueba lleva el torso desde su posición inicial hasta un punto libre al otro lado de la cama; el muestreo de trayectoria debe detectar `Bed.Mattress` y revertir el movimiento; CI valida todos los checks del informe | `solid_path_collision_rejected_and_rolled_back` y `WORLD_STATE_BLENDER_SYNC_REPORT_VALIDATION=PASS` | Muestreo de hasta 0.1 unidades con máximo 256 muestras; no es un solver de física continua y excluye otras piezas `character.*` |
| T-037 | La interfaz de sincronización puede cargar la última versión persistida o una versión explícita sin confundir fuentes | `tests/test_world3d_sync_state.py` prueba la carga JSON, la versión latest, la versión exacta, fuentes ambiguas y versiones inexistentes | `SnapshotSourceTests` en la suite de regresión rápida | La carga de datos se prueba sin Blender; la aplicación geométrica real se prueba por separado en T-034–T-036 |

## 3. Capacidades aún no verificadas / no implementadas

| ID futuro | Prueba que debe existir antes de integrar un generador de vídeo | Estado |
|---|---|---|
| F-001 | Cambiar cámara y demostrar que ninguna transformación canónica del mundo cambia | Parcial: prueba real de Blender integrada en CI; falta una capa de permisos/API que impida mutaciones externas |
| F-002 | Repetir una petición y conservar IDs de identidad, malla y entidad entre versiones | Parcial: builds deterministas conservan IDs y transforms; no existe todavía registro persistente de assets/identidades entre cambios intencionales |
| F-003 | Aplicar una orden explícita que contradice un default y demostrar que gana la orden, registrando el conflicto | Pendiente; contrato documentado, motor M15 no implementado |
| F-004 | Prompt sin muebles/armas/vehículos: comprobar que no aparecen entidades implícitas | Pendiente; el perfil declara prohibiciones, no hay compilador de prompt integrado |
| F-005 | Restaurar snapshot y reproducir eventos hasta obtener estado equivalente | Parcial: replay tras recarga cubre tres eventos y cuatro versiones persistidas; un puente inicial demuestra una cadena evento→persistencia→recarga→Blender para una malla. Falta restauración completa del mundo, base de datos multiusuario y registro de eventos duradero independiente |
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

| T-038 | Varios personajes, animales y objetos conservan IDs, referencias de identidad y transforms entre versiones persistidas de un mismo mundo | `WorldStateStoreTests.test_multiple_characters_animals_and_props_persist_across_versions`: crea entidades mediante eventos aprobados, persiste v1–v5, recarga la última versión y comprueba que todas siguen presentes | Suite `python3 -m unittest discover -s tests -v` | Prueba de contrato/persistencia JSON; no demuestra todavía identidad visual en vídeo ni creación/sincronización multi-entidad dentro de Blender |
