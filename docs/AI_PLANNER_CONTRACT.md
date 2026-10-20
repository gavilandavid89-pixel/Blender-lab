# ST-LAT AI Planner — contrato ejecutable v1

**Estado:** adaptador inicial implementado; la propuesta no se aplica automáticamente al mundo canónico.  
**Implementación:** `scripts/ai_world_planner.py`  
**Regresión:** `tests/test_ai_world_planner.py`  
**Prueba con proveedor real:** paso `Live AI planner contract test (Groq)` en `.github/workflows/blender.yml`.

## 1. Invariante de autoridad

La IA es un planificador no confiable. Puede interpretar lenguaje y sugerir operaciones; no es autoridad para cambiar el mundo. El estado canónico, los contratos Python y los validadores geométricos mandan siempre.

Flujo permitido:

1. Leer un snapshot de solo lectura.
2. Enviar al proveedor únicamente el contexto necesario.
3. Recibir JSON no confiable.
4. Decodificar JSON y comprobar el esquema operativo.
5. Rechazar el plan completo si hay un error.
6. Mostrar/guardar una propuesta marcada como `proposed`.
7. La función `scripts/world_state_transaction.py::commit_approved_transform` puede convertir una propuesta de una sola transformación en un evento aprobado y una nueva versión persistida, siempre que reciba aprobación explícita de un caller confiable y los límites AABB ya evaluados por Blender.
8. El adaptador de Blender debe ejecutar por separado la aplicación en escena, leer de vuelta los valores y comparar los límites reales; la transacción no guarda ni modifica por sí sola el archivo .blend.

No se permite que una respuesta del modelo escriba directamente snapshots, eventos, objetos Blender, archivos del proyecto o historial persistente. No se deben confundir `PROPOSAL_VALIDATED` y `WORLD_STATE_COMMITTED`: el primero no significa que el mundo haya cambiado.

## 2. Entrada aceptada

La petición contiene un snapshot JSON y una instrucción de usuario. El contexto enviado al proveedor se reduce a:

- `world_id`, `version`, `units`, `axes`, límites `bounds.min/max`;
- por entidad: `id`, `role`, `transform`, `identity_ref` y `attributes`.

La reducción de contexto es intencional, pero no reemplaza la validación del snapshot. Antes de ampliar el adaptador debe decidirse explícitamente qué campos son necesarios y cuáles son secretos o no deben enviarse al proveedor. No incluir credenciales en prompt, snapshot, artefactos ni logs.

### Convenciones espaciales

- Posición: vector de tres números finitos, en metros.
- Rotación: `rotation_euler_rad`, tres números finitos en radianes.
- Escala: vector de tres números finitos estrictamente positivos.
- Coordenadas: ejes definidos en el snapshot; no inferir una convención diferente.
- Posición dentro de `bounds.min/max`; la implementación inicial aplica además el suelo a entidades no cámara.

## 3. Forma de la respuesta

Raíz JSON obligatoria:

- `summary`: texto no vacío que describe la propuesta o explica la ambigüedad.
- `operations`: lista de operaciones.

Cada operación permitida tiene exactamente estos campos:

- `type`: solo `transform_updated`;
- `target_id`: ID de una entidad ya existente;
- `reason`: explicación no vacía;
- `transform`: objeto con exactamente `position`, `rotation_euler_rad` y `scale`.

No se aceptan campos desconocidos. Esta política de lista permitida es deliberada: evita que el modelo añada por su cuenta campos que un consumidor posterior pudiera interpretar como parentado, identidad, creación, eliminación, animación o ejecución.

## 4. Reglas de rechazo

El plan completo debe rechazarse si aparece cualquiera de estas condiciones:

1. La raíz no es un objeto JSON.
2. Falta el resumen, está vacío o `operations` no es una lista.
3. El snapshot no contiene una lista de entidades o límites vectoriales válidos.
4. Un ID del snapshot está vacío o duplicado.
5. Una operación no es un objeto o usa un tipo distinto de `transform_updated`.
6. El destino no existe o el mismo destino aparece más de una vez.
7. Falta `reason`, `transform` o cualquier vector obligatorio.
8. Un vector tiene longitud distinta de tres, booleanos, texto, NaN o Infinity.
9. La escala contiene cero o valores negativos.
10. La posición incumple límites duros o suelo.
11. Aparece un campo protegido o desconocido, incluidos identidad, rol, relación padre-hijo, asset o apariencia.
12. La transformación contiene campos extra o carece de campos requeridos.
13. El proveedor falla, la respuesta no contiene JSON o se agota el tiempo de espera.

Los errores se devuelven como fallo de planificación; no se debe “arreglar” automáticamente una propuesta insegura y después fingir que la IA la produjo correctamente. Si se implementa una reparación, debe ser un paso separado, limitado, trazable y volver a ejecutar toda la validación desde cero.

## 5. Ambigüedad y ausencia de cambios

Una orden ambigua puede devolver `operations: []` con explicación. La lista vacía no significa que el objetivo se haya cumplido. La capa de orquestación debe distinguir como mínimo:

- `proposed`: el JSON cumple el contrato de propuesta;
- `needs_clarification`: no hay información suficiente para una operación segura;
- `rejected`: el plan viola un contrato;
- `applied`: una fase de aplicación independiente confirmó el cambio;
- `not_verified`: no hay evidencia suficiente para afirmar el resultado.

El adaptador actual emite `proposed` para planes estructuralmente válidos, incluso si la lista de operaciones está vacía. La clasificación explícita de ambigüedad es una mejora futura y no debe darse por implementada.

## 6. Transacción de estado implementada y límites

El módulo `scripts/world_state_transaction.py` ofrece una primera transacción de una sola transformación. Verifica la versión esperada frente al último snapshot persistido, exige etiqueta explícita de aprobación, valida que el destino siga existiendo, prohíbe cambios de rotación y escala, exige AABB evaluado con tipo `aabb`, reproduce el evento aprobado, comprueba la versión siguiente y lee de vuelta el snapshot persistido. Los fallos de validación ocurren antes de guardar una versión nueva.

La etiqueta `approved_by` es evidencia/auditoría, no una credencial criptográfica. El caller debe aplicar una puerta de aprobación autenticada. Además, la tienda es de un solo escritor: no proporciona un compare-and-swap atómico entre procesos ni bloqueo distribuido. No ejecutar varios escritores concurrentes sobre la misma tienda.

**Todavía no es una transacción de extremo a extremo con Blender.** La integración debe primero aplicar en una escena de staging o poder restaurarla con certeza, medir los límites evaluados, y solo después persistir. La función transaccional no escribe el archivo `.blend`; no afirmar que la escena y el snapshot se confirmaron juntos.

## 7. Pruebas y puertas de CI

### Pruebas sin red

`python3 -m unittest discover -s tests -v` cubre el contrato puro. Los casos positivos y negativos deben comprobar al menos IDs existentes, límites, vectores finitos, escala, operaciones duplicadas, identidad protegida, campos desconocidos, razón no vacía, IDs duplicados del snapshot y límites invertidos.

### Prueba real de proveedor

Cuando existe el secreto `GROQ_API_KEY`, CI solicita una sola operación concreta para `char.001` y comprueba de forma independiente:

- estado `proposed`;
- exactamente una operación;
- tipo `transform_updated` y destino exacto `char.001`;
- posición exacta `[0.3, 0.0, 1.0]`;
- rotación y escala idénticas al snapshot;
- ninguna operación sobre `prop.ball.001`;
- ningún campo de identidad o relación protegido.

Si el secreto no está configurado, el paso declara `SKIP`; esa ejecución no prueba el comportamiento real del proveedor. La cuota, disponibilidad o conectividad son dependencias externas y deben distinguirse de fallos de contrato.

### Prueba de aplicación pendiente

La prueba real de proveedor solo verifica una propuesta. No prueba todavía que un plan de lenguaje natural pueda convertirse en evento aprobado, persistirse y aplicarse a Blender. El siguiente módulo debe probar una transacción de extremo a extremo: validar contra versión vigente, rechazar snapshot obsoleto, crear evento aprobado, aplicar de forma atómica, comprobar invariantes y rollback completo si falla cualquier postcondición.

## 8. Límites explícitos

- No crea ni elimina entidades.
- No cambia identidad, rol, parentado, asset ni apariencia.
- No ejecuta código generado por el modelo.
- No aplica automáticamente transformaciones.
- No realiza planificación de rutas, animación articulada, resolución de colisiones completa ni evaluación visual de vídeo.
- La validación de posición del adaptador no reemplaza el contrato completo del mundo ni el chequeo de AABB/colisiones en Blender.
- Una propuesta correcta no garantiza que la transformación sea físicamente alcanzable o visualmente correcta.

## 9. Próximos módulos recomendados

- **AI-02 — Normalizador de intención:** traducir frases a una intención tipada; preservar explícitos, marcar inferencias y devolver preguntas ante ambigüedad.
- **AI-03 — Comparador de restricciones:** comparar plan con versión vigente y ledger de restricciones; informar conflictos sin resolverlos silenciosamente.
- **AI-04 — Transacción Blender/snapshot de extremo a extremo:** conectar la transacción de estado existente con staging de Blender, medición de AABB, read-back, compensación y persistencia coordinada.
- **AI-05 — Adaptador Blender controlado:** aplicar solo eventos validados a entidades mapeadas, verificar lectura de vuelta, AABB y objetos no objetivo.
- **AI-06 — Auditor de evidencia:** registrar hash de snapshot, prompt, modelo, respuesta redactada de secretos, resultado de validación, evento y artefactos.
- **AI-07 — Evaluador de continuidad:** más adelante, comparar fotogramas/vídeo con identidad, presencia de entidades, geometría, pose y cámara; “no medido” nunca equivale a “aprobado”.

Cada módulo debe tener contrato versionado, límites explícitos, pruebas positivas/negativas, evidencia reproducible y un estado de implementación honesto.
