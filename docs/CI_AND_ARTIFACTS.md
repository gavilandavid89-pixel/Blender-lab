# ST-LAT Lab — guía de CI, artefactos y diagnóstico

## Qué hace la acción

Workflow: `.github/workflows/blender.yml` — **Blender Headless Lab**.

Orden de ejecución:

1. Descarga el repositorio.
2. Valida el perfil de escena neutra.
3. Ejecuta autopruebas de los validadores del manifiesto y del informe de movimiento.
4. Ejecuta las pruebas de regresión rápidas de `tests/`.
5. Instala las bibliotecas de runtime y Blender 5.2.2.
6. Construye la escena desde `scripts/world3d_probe.py`.
7. Abre el archivo guardado y prueba recorridos con `scripts/world3d_validate_motion.py`.
8. Valida el informe persistido de movimiento y el manifiesto de escena con validadores independientes.
9. Prueba el puente de sincronización de estado sobre la escena Blender guardada: preflight, aplicación de transform, AABB evaluada y rollback ante datos contradictorios.
10. Comprueba que los archivos de salida existen y no están vacíos.
11. Publica `stlat-world3d-output`, incluso si un paso anterior falla, para conservar diagnósticos disponibles.

Los pasos rápidos se ejecutan antes de descargar Blender para detectar errores de contrato sin gastar tiempo de render. El job tiene un límite de 20 minutos. Los cambios en `scripts/**`, `tests/**`, `docs/**`, `README.md` o el workflow activan CI; también se puede iniciar manualmente con **Actions → Blender Headless Lab → Run workflow**.

## Archivos del artefacto

| Archivo | Para qué sirve | Qué mirar primero |
|---|---|---|
| `stlat-world3d.blend` | Escena de Blender guardada y editable | Objetos, roles, geometría, cámaras y posición inicial |
| `stlat-world3d-main.png` | Vista principal | Composición y escena general; no es prueba de física |
| `stlat-world3d-topdown.png` | Vista cenital | Distribución XY y relaciones espaciales |
| `stlat-world3d-manifest.json` | Registro estructurado del mundo | `schema`, `status`, `axes`, `room_interior`, `objects`, `checks` |
| `stlat-world3d-motion-validation.json` | Evidencia de trayectorias | `checks`, `safe_walk_forward`, `intentionally_blocked_toward_bed`, `intentionally_outside_room` |
| `blender.log` | Salida de Blender y errores | Primer traceback y último bloque del log |
| `exit-code.txt` | Código de la construcción | `0` indica que la construcción terminó correctamente |
| `motion-validation-exit-code.txt` | Código de la validación de movimiento | `0` indica que el script de movimiento terminó correctamente |

| `stlat-world-state-blender-sync.json` | Resultado del puente estado persistente → Blender | `checks`, `applied_entity_ids` y el estado de rechazo/rollback |

Los artefactos de Actions se conservan durante 14 días. Si un paso falla, abre la ejecución fallida y descarga el artefacto si está disponible; el paso de publicación usa `if: always()` para intentar conservar los archivos parciales.

## Cómo interpretar los informes

### Manifiesto

- `status: success` indica que el generador considera que la exportación terminó bien; el validador independiente comprueba además estructura, roles, IDs, vectores, AABB, cámaras declaradas y archivos de render.
- `id` debe ser único dentro del manifiesto. Esta comprobación todavía no demuestra identidad persistente entre distintas ejecuciones.
- `role` vincula el objeto a una función semántica. Un objeto sin clasificación no debe tratarse como entidad válida.
- `aabb_world` es una caja delimitadora alineada a los ejes; puede sobreestimar el volumen real de objetos rotados o irregulares.

### Informe de movimiento

- `initial_pose_is_valid`: el personaje proxy empieza dentro del espacio permitido y sin colisión con los obstáculos considerados.
- `safe_path_is_collision_free`: las muestras del recorrido libre no encontraron violaciones.
- `bed_path_hits_bed_geometry`: el recorrido deliberadamente bloqueado encontró al menos una colisión con geometría cuyo nombre empieza por `Bed.`.
- `room_boundary_violation_detected`: la posición deliberadamente externa tiene partes del personaje fuera de los límites.
- `bed_geometry_collision_hits`: número de coincidencias registradas entre partes del personaje y geometría de la cama.

**Importante:** los recorridos se muestrean en 49 posiciones y las colisiones usan AABB. Esto no certifica ausencia de colisiones entre muestras ni sustituye una simulación física continua.

## Diagnóstico rápido

| Síntoma | Posible causa | Acción |
|---|---|---|
| Falla antes de instalar Blender | Regresión de contrato o test rápido | Leer el primer error del paso; reproducir los comandos rápidos en la sección de pruebas del README |
| `duplicate entity id` | Dos objetos exportan el mismo ID | Corregir el origen del ID en el constructor; no ocultar el error con un renombrado posterior |
| `required semantic roles missing` | Se eliminó, renombró o dejó sin rol un objeto necesario | Revisar `stlat_role` en `world3d_probe.py` y el manifiesto exportado |
| Falla `initial_pose_is_valid` | El spawn está fuera del cuarto o solapa un obstáculo | Revisar la posición de anclaje y las piezas del personaje |
| Ruta segura tiene violaciones | El camino supuesto como libre no lo está | Revisar coordenadas, obstáculos y muestreo; no rebajar el check para hacer pasar CI |
| No se detecta la cama | El objetivo no cruza la geometría de la cama o los nombres/roles no coinciden | Inspeccionar `bed_geometry_collision_hits`, `obstacle_count` y los objetos `Bed.*` |
| No se detecta salida | El destino no coloca ninguna parte fuera de los límites | Revisar límites del cuarto y `outside_parts` |
| Manifiesto válido, informe de movimiento inválido | El formato existe, pero la evidencia requerida está ausente o es contradictoria | Corregir la generación o la validación; no tratar la presencia del JSON como éxito |
| Render vacío o ausente | Blender falló antes de guardar o renderizar | Revisar `blender.log` y los códigos de salida |

## Reglas para mantener CI confiable

- No eliminar una prueba porque detectó un fallo real; corregir el código o justificar/documentar un cambio de contrato.
- No considerar verde una ejecución cancelada. Solo `conclusion: success` cuenta como CI aprobada.
- Evitar commits consecutivos innecesarios mientras Blender está renderizando: el workflow usa concurrencia con cancelación de ejecuciones anteriores de la misma rama.
- Al cambiar un formato de informe, actualizar a la vez el generador, el validador independiente, las pruebas negativas, la matriz y esta guía.
- Un artefacto publicado no significa que la ejecución haya pasado. Revisar siempre el resultado del workflow y los informes.

## Estado de alcance

La CI prueba el laboratorio 3D actual. No prueba aún identidad visual persistente, replay de memoria, obediencia a prompts, generación de vídeo, ni evaluación temporal de fotogramas. Esas capacidades requieren sus propios módulos, datos de prueba y criterios de aprobación antes de declararse implementadas.


## Puente inicial de estado hacia Blender

`scripts/world3d_sync_state.py` acepta un snapshot con `--snapshot state.json`. Antes de tocar objetos, valida el contrato del estado, la unicidad de IDs de escena, la correspondencia de IDs y roles y que los objetivos sean mallas sin padre. Aplica solo transforms; después verifica las transforms leídas y los bounds AABB evaluados. Si una comprobación posterior falla, restaura los transforms originales.

El puente no crea ni elimina objetos, no cambia jerarquías, no sincroniza cámaras/luces ni animación, y **no guarda el archivo .blend**. La autoprueba integrada en CI no sustituye pruebas de escenas complejas ni autoriza scripts arbitrarios.
