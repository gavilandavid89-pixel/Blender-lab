# ST-LAT Engine — arquitectura funcional v0.1

**Estado:** especificación de diseño, no afirmación de que todos los módulos estén implementados.  
**Principio:** el mundo y su estado temporal son la fuente de verdad; el generador de vídeo es un componente subordinado que produce una propuesta visual que debe verificarse.

## 1. Objetivo y límites

ST-LAT busca reducir invenciones visuales: cambios de identidad, proporciones inestables, objetos que aparecen/desaparecen, atravesar geometría, posiciones imposibles, saltos temporales y cámaras incompatibles con la escena.

No se promete eliminar toda alucinación. La estrategia es convertir las partes importantes del prompt en restricciones explícitas, generar referencias verificables, evaluar el resultado y rechazar o corregir los segmentos que violen las restricciones.

### Invariantes principales

1. **Identidad persistente:** un personaje mantiene un ID, sus rasgos aprobados y su escala base entre planos.
2. **Estado canónico:** cada entidad tiene una única transformación y estado vigentes por instante de la simulación.
3. **Geometría explícita:** los objetos relevantes tienen límites espaciales y una clase de colisión.
4. **Causalidad temporal:** el estado de t+1 deriva del estado de t mediante una acción o evento válido.
5. **Cámara separada del mundo:** mover la cámara cambia la observación, no la ubicación real de los objetos.
6. **Trazabilidad:** cada restricción indica su origen (prompt, usuario, mundo o regla del sistema) y confianza.
7. **Fallo visible:** si una condición no se puede satisfacer o comprobar, se marca como desconocida/fallida; nunca como validada.

## 2. Módulos propuestos

| ID | Módulo | Responsabilidad | Entradas | Salidas | Estado |
|---|---|---|---|---|---|
| M00 | Orquestador | Gestiona dependencias, reintentos, presupuesto y estado final | petición + configuración | plan de ejecución + resultado | Diseño |
| M01 | Compilador de prompt | Convierte lenguaje natural en entidades, acciones, tiempo, cámara y restricciones | prompt + contexto | plan estructurado + ambigüedades | Diseño |
| M02 | Registro de identidad | Mantiene IDs y atributos estables de personajes/objetos persistentes | referencias aprobadas + perfil | perfil de identidad versionado | Diseño |
| M03 | Estado del mundo | Mantiene entidades, transformaciones, jerarquías, unidades y estado por instante | entidades + eventos | estado versionado | Prototipo parcial: manifiesto espacial |
| M04 | Constructor de escena | Crea/actualiza geometría, materiales, jerarquías y colisionadores | estado del mundo | escena 3D + IDs ligados a geometría | Prototipo parcial: habitación |
| M05 | Validador espacial | Detecta límites, intersecciones, oclusiones y posiciones inválidas | geometría + estado | infracciones con severidad y evidencia | Prototipo parcial: AABB/trayectorias |
| M06 | Planificador de movimiento | Convierte acciones en trayectorias y poses posibles | acción + estado + colisiones | trayectoria temporal + eventos | Diseño |
| M07 | Planificador de cámara | Define cámara, encuadre, lente, trayectoria y visibilidad | intención visual + mundo | cámaras y tomas | Parcial: cámaras de referencia |
| M08 | Generador de referencias | Produce RGB, profundidad, normales, máscara por entidad, silueta y pose | estado + cámara + tiempo | paquete de condicionamiento | Diseño |
| M09 | Adaptador del generador de vídeo | Traduce referencias al formato que admita un modelo concreto | referencias + prompt | vídeo candidato + metadatos | No implementado |
| M10 | Evaluador temporal | Compara fotogramas con estado esperado, identidad, geometría y continuidad | vídeo candidato + referencias | métricas + infracciones | No implementado |
| M11 | Reparador/reintento | Corrige plan o condicionamiento cuando sea corregible | informe + estado | nueva propuesta o rechazo | No implementado |
| M12 | Memoria de proyecto | Guarda mundo, perfiles, decisiones aprobadas y versiones entre sesiones | eventos + aprobaciones | estado persistente recuperable | Diseño |
| M13 | Paquete de auditoría | Guarda versiones, parámetros, fuentes, pruebas, métricas y artefactos | resultados de módulos | informe reproducible | Parcial: artefactos CI y JSON |

## 3. Contratos entre módulos

### M01 — Compilador de prompt

Debe producir un plan estructurado, no instrucciones vagas solamente. Como mínimo: sujetos (IDs existentes o nuevos), acciones (actor, verbo, objetivo y orden), tiempo (duración y eventos), espacio (posiciones y relaciones), cámara, restricciones duras, preferencias blandas e incógnitas.

**Regla de omisión:** si el prompt no determina un detalle, usar el valor neutral del proyecto o conservar el estado previo. No inventar un cambio persistente para rellenar un hueco.

### M02 — Registro de identidad

Cada perfil separa identidad semántica, geometría base (altura, proporciones, escala y rig), rasgos visuales aprobados, referencias fuente, tolerancias por atributo, versión y procedencia de cada cambio. Una toma nueva no puede redefinir la identidad por sí sola; solo una edición aprobada crea una versión nueva.

### M03 — Estado del mundo

Cada entidad tiene ID estable, rol semántico, transformación, dimensiones/volumen, relación padre-hijo, propiedades físicas pertinentes y estado temporal. La escena renderizada es una vista del estado, no la única fuente de verdad.

Separar estado estático (arquitectura/muebles), dinámico (personajes/puertas/objetos movidos), de observación (cámara/lente/encuadre) y narrativo (acción actual/eventos).

### M05 — Validador espacial

Orden de comprobación: esquema y unidades; entidades obligatorias; límites y zonas permitidas; colisiones del volumen del personaje; continuidad de trayectoria; relaciones semánticas (objeto agarrado asociado a la mano); coherencia entre estado canónico y escena exportada.

Cada infracción devuelve rule_id, entidad, tiempo, severidad, confianza, magnitud del error y evidencia reproducible. AABB sirve como filtro rápido; colisiones críticas deben migrar a volúmenes más precisos.

### M06 — Planificador de movimiento

Una acción se describe como secuencia temporal, no solo como posición final. Caminar valida el volumen corporal a lo largo del recorrido; agarrar valida aproximación, contacto, unión temporal objeto-mano y liberación.

Distinguir ruta imposible, ruta posible pero no planificada, información insuficiente y colisión intencional (golpear, empujar o romper).

### M07/M08 — Cámara y referencias

La cámara define cómo se observa el mundo, no dónde está. Por toma generar, cuando sea posible: RGB, profundidad, normales, máscara de IDs por entidad, silueta/pose, parámetros intrínsecos/extrínsecos de cámara, estado del mundo y timestamp. Las referencias deben compartir resolución, encuadre, coordenadas y marcas temporales. Cambiar cámara no puede interpretarse como movimiento de objeto.

### M09 — Adaptador de vídeo

El núcleo no debe depender de un proveedor. Cada adaptador declara capacidades reales: duración, resolución, referencias admitidas, controles de cámara, semillas y límites. Si un control no existe en el modelo, se marca como no garantizado y se comprueba después.

### M10 — Evaluador temporal

Evaluar fotogramas regularmente y en eventos importantes. Métricas separadas: identidad/proporciones, presencia de entidades, posición/escala proyectada, penetración, profundidad/oclusión, consistencia de cámara, continuidad/velocidad y correspondencia acción-resultado.

Una infracción dura (atravesar una pared) no puede quedar oculta por una buena puntuación estética. Un fotograma no verificable no equivale a uno aprobado.

### M11 — Reparación controlada

Prioridad: reparar plan/estado si es imposible; regenerar referencias; reintentar solo el segmento afectado; reevaluar; aceptar, pedir aclaración o rechazar. Limitar reintentos y conservar cada candidato con su informe. Nunca cambiar silenciosamente la verdad del mundo para justificar un vídeo incorrecto.

## 4. Modelo temporal y memoria

Representar la acción mediante estados con timestamps explícitos. Interpolar solo cuando el movimiento lo permita y volver a comprobar la trayectoria. Agarrar, soltar, sentarse, abrir una puerta o entrar en una habitación son eventos que cambian relaciones o estados, no solo píxeles.

La memoria guarda versión del mundo, estado anterior/siguiente, evento que justifica cada cambio, actor responsable, timestamp de simulación, fuente de la instrucción y validaciones ejecutadas.

## 5. Severidad de errores

- **E0 — Bloqueante:** identidad equivocada, colisión imposible, entidad persistente desaparecida, límites violados.
- **E1 — Grave:** trayectoria incoherente, escala/proporción fuera de tolerancia, oclusión imposible.
- **E2 — Moderado:** pose aproximada, temporización o movimiento fuera de preferencia.
- **E3 — Estético:** diferencias de iluminación/textura que no contradicen el mundo.

E0 nunca se compensa con una buena puntuación estética. La tolerancia se configura por regla y unidad; no existe una tolerancia universal.

## 6. Secuencia de implementación

1. Fundación comprobable: esquema de mundo, IDs, unidades, límites y pruebas CI.
2. Colisiones/movimiento: volumen corporal, geometría, trayectorias y rutas bloqueadas/libres.
3. Estado temporal: poses, eventos, objetos agarrados, cámara separada y guardado/reanudación.
4. Referencias por fotograma: RGB, profundidad, máscaras y metadatos.
5. Evaluación de vídeo: comparación con referencias y métricas por regla.
6. Adaptador de modelo: solo tras comprobar los controles reales del proveedor.
7. Reparación: reintentos limitados, reevaluación y auditoría.
8. Robustez: cambios de cámara, oclusiones, varios personajes, objetos dinámicos, escenas largas y ambigüedades.

## 7. Pruebas de aceptación mínimas

- La misma escena/configuración produce los mismos IDs y estado lógico.
- Una trayectoria libre no se marca como bloqueada.
- Una trayectoria que cruza pared/cama genera una infracción identificable.
- Un personaje fuera del volumen permitido produce error de límites.
- Cambiar cámara no cambia coordenadas del mundo.
- Un objeto agarrado no flota ni cambia de dueño sin evento de liberación.
- Un personaje conserva ID y atributos aprobados entre tomas.
- Un fotograma sin datos suficientes se marca como no verificable.
- Un resultado rechazado no sobrescribe el último estado aprobado.

## 8. Riesgos técnicos conocidos

- AABB produce falsos positivos en geometría rotada o irregular.
- Muestrear una ruta puede saltarse colisiones entre muestras.
- Un proxy segmentado no representa una malla deformable.
- El generador puede ignorar controles; el resultado debe evaluarse.
- Profundidad y máscaras estimadas desde vídeo pueden fallar y no son verdad absoluta.
- Conservar un ID no demuestra por sí solo identidad visual.
- Cada prueba debe declarar qué comprueba y qué no.

## 9. Estado real

- Implementado parcialmente: habitación, personaje proxy, cámaras, manifiesto y renders.
- Implementado parcialmente: prueba de trayectorias AABB con casos positivos/negativos; pendiente de confirmación CI.
- No implementado: identidad final, rig, memoria entre sesiones, referencias temporales, adaptador de vídeo, evaluación de fotogramas y reparación.
