# ST-LAT Engine — contratos operativos de módulos v1

**Documento de diseño.** Los estados «diseño», «parcial» e «implementado» deben mantenerse separados. Tener un contrato no significa que exista código que lo ejecute.

## 1. Flujo de extremo a extremo

1. M00 recibe la petición, el perfil del proyecto y el presupuesto de ejecución.
2. M01 convierte el prompt en una intención estructurada y enumera ambigüedades.
3. M14 selecciona un perfil de escena neutra cuando el proyecto o el prompt no fijan entorno.
4. M02 resuelve identidades existentes y propone nuevas identidades solo cuando el usuario introduce sujetos nuevos.
5. M03 crea una versión candidata del estado del mundo; M15 conserva el origen y prioridad de cada restricción.
6. M04 construye la escena 3D y registra la correspondencia entre entidad semántica y objeto geométrico.
7. M05 valida límites, colisiones y coherencia geométrica; M06 planifica movimientos válidos.
8. M07 define cámaras sin cambiar el estado del mundo; M08 produce referencias desde el estado aprobado.
9. M09 entrega las referencias al generador externo y recoge el vídeo candidato con sus metadatos.
10. M10 evalúa el vídeo frente al plan y las referencias.
11. M11 solicita una reparación limitada o marca el resultado como rechazado/no verificado.
12. M12 guarda solo los cambios aprobados y versionados; M13 empaqueta pruebas, evidencia y artefactos.

## 2. Contrato común de módulo

Cada módulo debe declarar:
- module_id, module_version, status y versión de esquema de entrada/salida.
- Entradas obligatorias y opcionales, con unidades y convenciones.
- Salidas estructuradas, no solo texto libre.
- Precondiciones y postcondiciones comprobables.
- Errores tipados, severidad y si permiten reintento.
- Procedencia: qué dato originó cada decisión.
- Efectos secundarios permitidos. Por defecto, los módulos no modifican memoria persistente.
- Un conjunto de pruebas deterministas para el comportamiento central.

Ningún módulo puede convertir un dato ausente en un hecho confirmado sin etiquetarlo como valor por defecto o inferencia incierta.

## 3. Contratos de los módulos

| ID | Entradas | Salidas obligatorias | No debe hacer | Prueba mínima |
|---|---|---|---|---|
| M00 Orquestador | solicitud, configuración, presupuesto | plan, estado final, tiempos, errores | ocultar fallos o declarar éxito si falta un paso requerido | fallo de un módulo se propaga como estado no exitoso |
| M01 Compilador de prompt | prompt, contexto de proyecto | sujetos, acciones, objetivos, tiempos, cámara, restricciones, ambigüedades | añadir historia, objetos o motivaciones no pedidos | prompt mínimo produce solo entidades solicitadas |
| M02 Registro de identidad | referencias aprobadas, ID de proyecto | perfil versionado, rasgos invariantes, escala y referencias | sustituir identidad por un parecido nuevo | misma identidad recupera mismo ID y atributos protegidos |
| M03 Estado del mundo | estado anterior, propuestas de cambio, eventos | nueva versión candidata, entidades, transformaciones y eventos | sobrescribir el historial o mover objetos por conveniencia | replay de los mismos eventos produce estado equivalente |
| M04 Constructor de escena | estado candidato, perfil de escena | escena 3D, mapa entidad↔objeto, geometría y roles | inventar props narrativos o perder IDs semánticos | cada entidad requerida tiene correspondencia y cada objeto técnico está clasificado |
| M05 Validador espacial | geometría, límites, trayectoria | infracciones, evidencia, severidad y confianza | asumir que muestras discretas prueban física perfecta | colisión deliberada detectada y recorrido libre aceptado |
| M06 Planificador de movimiento | acción, pose inicial, colisionadores, límites | trayectoria temporal, poses y eventos previstos | atravesar obstáculos sólidos o teletransportar sin evento | ruta bloqueada produce fallo o ruta alternativa válida |
| M07 Planificador de cámara | intención visual, geometría, sujeto objetivo | poses de cámara, lente, encuadre y visibilidad | alterar las transformaciones del mundo | cambiar de cámara deja intacto el estado canónico |
| M08 Generador de referencias | escena aprobada, cámara, tiempo | RGB, profundidad/normal/máscaras cuando estén soportadas, metadatos | presentar una referencia obsoleta como actual | cada imagen identifica versión de mundo, cámara y timestamp |
| M09 Adaptador de vídeo | referencias, prompt, capacidades del proveedor | vídeo candidato, parámetros, versión del modelo y limitaciones | afirmar que el proveedor obedeció sin medirlo | entrada y salida tienen trazabilidad reproducible |
| M10 Evaluador temporal | vídeo, referencias, trayectoria y perfil de identidad | métricas por fotograma/segmento, evidencia, unknowns | confundir falta de evidencia con aprobación | cambio de vestimenta/posición no autorizado se marca |
| M11 Reparador | informe de infracciones, restricciones, presupuesto | parche propuesto, nueva ejecución o rechazo | cambiar silenciosamente identidad o intención para pasar | límite de intentos y preservación de restricciones |
| M12 Memoria de proyecto | cambios aprobados, evidencias, versiones | snapshot, historial de eventos, referencias persistentes | admitir como verdad un fotograma no validado | un candidato rechazado no altera el snapshot canónico |
| M13 Auditoría | artefactos, informes, parámetros y versiones | manifiesto de ejecución, enlaces, pruebas y estado final | omitir una infracción o reescribir el resultado | otro proceso puede comprobar qué se ejecutó y con qué datos |
| M14 Selector de escena neutra | prompt compilado, perfiles aprobados, tarea | profile_id, versión, valores aplicados y razón de selección | tratar una plantilla técnica como entorno narrativo confirmado | prompt exterior no selecciona empty_room |
| M15 Registro de restricciones | restricciones, origen, prioridad y alcance | ledger ordenado, conflictos y resolución | dejar que un default venza una instrucción explícita | conflicto entre prompt y default prioriza el prompt y registra el conflicto |
| M16 Registro de recursos | IDs de malla, textura, rig, imagen, licencia/procedencia | recurso versionado, hash cuando sea posible, compatibilidad | sustituir un recurso sin registrar el cambio | mismo asset ID apunta a versión conocida; sustitución genera nueva versión |

## 4. Prioridad y resolución de conflictos

Orden de prioridad recomendado:
1. Restricciones de seguridad y límites técnicos duros.
2. Instrucción explícita vigente del usuario.
3. Decisiones aprobadas y persistentes del proyecto.
4. Estado canónico del mundo y continuidad ya confirmada.
5. Restricciones derivadas de geometría, física o cámara.
6. Valores de plantilla neutra.
7. Inferencias de baja confianza.

Este orden no permite que una instrucción cambie silenciosamente una identidad persistente. Si una instrucción nueva contradice una decisión aprobada, se crea una propuesta de cambio explícita y se registra qué versión reemplazaría.

## 5. Estados normalizados

Estados de ejecución:
- planned: preparado, aún no ejecutado.
- running: en ejecución.
- passed: las comprobaciones obligatorias terminaron y pasaron.
- failed: una comprobación obligatoria falló.
- blocked: no se puede continuar por conflicto o falta de dato esencial.
- partial: algunas salidas existen, pero no todas las pruebas requeridas.
- not_verified: se produjo una salida sin evidencia suficiente para certificarla.

Estados de evidencia:
- confirmed: apoyado por dato explícito o prueba válida.
- defaulted: valor de plantilla aplicado deliberadamente.
- inferred: inferencia con confianza registrada.
- unknown: no se conoce.
- contradicted: evidencia incompatible con la afirmación.

passed nunca significa «vídeo perfecto»; significa que las comprobaciones especificadas para esa ejecución pasaron.

## 6. Errores y reparación

- E0 bloqueante: identidad equivocada, estado corrupto, límite duro violado, salida faltante. No se entrega como resultado aprobado.
- E1 grave: colisión, teleportación, objeto persistente que desaparece, acción imposible o cambio no autorizado. Reparar o rechazar.
- E2 moderado: desviación de encuadre, error de pose, escala visual inconsistente o máscara incompleta. Reparación si no altera la intención.
- E3 estético: diferencias de textura, grano o iluminación no fijadas por el usuario. No justificar cambios semánticos por motivos estéticos.

Cada reparación debe tener un presupuesto máximo, conservar las restricciones originales y mostrar qué cambió. Si no puede arreglarse sin violar una restricción superior, se detiene.

## 7. Requisitos de escenas neutras

El selector M14 usa el contrato de [escenas neutras](NEUTRAL_SCENES.md) y el esquema [scene-profile.v1](schemas/scene-profile.v1.schema.json). El perfil de ejemplo es [neutral-studio.v1.json](examples/neutral-studio.v1.json).

La plantilla solo decide valores de presentación. No puede añadir sujetos, utilería narrativa, acciones, emociones, ropa distintiva o relaciones no solicitadas. Los objetos técnicos deben ir en capas de cámara, iluminación o depuración y no filtrarse al render final.

## 8. Estado versionado: primera capa ejecutable

`scripts/world_state_contract.py` implementa validaciones puras, sin dependencias externas, para snapshots `stlat.world-state.v1`:

- valida unidades, ejes, bounds, vectores finitos, escala positiva e IDs únicos;
- exige linaje de versión contiguo (`version = parent.version + 1`);
- exige eventos explícitos aprobados para crear/eliminar entidades;
- protege `identity_ref`, `identity_signature`, `asset_id` y `appearance_id` contra cambios silenciosos;
- comprueba que una operación marcada como «solo cámara» cambie una cámara y no altere ninguna entidad no cámara.

Las pruebas están en `tests/test_world_state_contract.py`. `scripts/world_state_replay.py` implementa replay determinista en memoria para `entity_created`, `entity_removed`, `transform_updated`, `entity_role_change_approved` e `identity_change_approved`: cada evento aprobado crea una versión enlazada, actualiza el timestamp, valida la transición y rechaza operaciones desconocidas o inconsistentes. `scripts/validate_world_replay.py` ejecuta pruebas positivas/negativas y guarda `artifacts/stlat-world-state-replay.json`.\n\nEsta es una **primera capa de replay sobre snapshots JSON**, no todavía el módulo M03/M12 integrado: no persiste snapshots, no reproduce aún eventos de relaciones ni sincroniza cambios con una escena Blender. El campo `approved` es evidencia declarada, no autorización criptográfica; el sistema de permisos real todavía debe conectarse.

## 9. Qué está probado hoy

- La acción de GitHub construye una habitación 3D de prueba, genera renders y manifiesto, ejecuta comprobaciones espaciales aproximadas y publica artefactos.
- La validación de movimiento usa muestras de trayectoria y AABB; no es una simulación física completa.
- El personaje es un proxy segmentado, no un rig con identidad persistente.
- El selector de escenas, el ledger de restricciones, el registro de recursos, la generación de referencias multicanal, el adaptador de vídeo y el evaluador temporal siguen siendo contratos de diseño hasta que haya código y pruebas.

## 10. Siguiente orden de implementación

1. Validar esquema de perfiles y ejemplo en CI.
2. Añadir pruebas de contrato para defaults, prioridad y ausencia de props implícitos.
3. Exportar un manifiesto de escena con IDs y origen de cada valor.
4. Mejorar colisión desde AABB a cápsulas/volúmenes y pruebas de trayectorias más densas.
5. Generar referencias frontales, laterales y cenitales asociadas a la misma versión de mundo.
6. Añadir perfiles de identidad/rig y pruebas de continuidad.
7. Solo después conectar un generador de vídeo y medir su obediencia real.


## 9. Prueba ejecutable de aislamiento de cámara

`scripts/world3d_validate_camera_isolation.py` abre la escena guardada desde el workflow, registra las firmas de todos los objetos no cámara, modifica posición/rotación/lente de `Camera.Main`, alterna la cámara activa y vuelve a comparar transformaciones, dimensiones y hash de vértices de malla evaluados en coordenadas de mundo. Escribe `artifacts/stlat-world3d-camera-isolation.json`; el validador independiente `scripts/validate_camera_isolation_report.py` comprueba la evidencia. La escena modificada no se guarda. Esta prueba detecta efectos colaterales de las operaciones probadas, pero no es un sistema de permisos que impida que un script externo cambie objetos.


## 10. Huella reproducible de geometría

Cada registro de malla del manifiesto `stlat.world3d.v1` incluye cantidades de vértices/aristas/polígonos y `mesh_geometry_sha256`, calculado sobre la geometría evaluada de Blender en coordenadas locales, con coordenadas redondeadas a seis decimales y vértices/aristas/caras canonizados por coordenadas, no por índices internos. La comparación de builds independientes incluye esta huella, de modo que un cambio de topología o forma no pase inadvertido solo porque el ID, la transformación o el AABB se mantengan. No es una huella de materiales, rig, texturas ni píxeles renderizados.
