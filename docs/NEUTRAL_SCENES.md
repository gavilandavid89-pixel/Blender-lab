# ST-LAT — escenas neutras y valores por defecto v1

**Estado:** contrato de diseño. Los perfiles descritos aquí no se consideran implementados hasta que el constructor de escenas y sus pruebas los consuman.

## 1. Qué significa «escena neutra»

Una escena neutra es una plantilla controlada para resolver lo que el usuario no especificó sin inventar historia, objetos, relaciones ni acciones. No significa que todas las escenas deban ser una habitación vacía. Los valores no especificados se resuelven mediante un perfil explícito, reproducible y reemplazable.

Regla principal: **un valor por defecto puede completar la presentación, pero no puede crear hechos narrativos**.

- Se puede elegir luz suave y una cámara de referencia para hacer visible al sujeto.
- No se puede añadir una espada, mascota, ventana, segundo personaje o tormenta porque «quedan bien».
- Si el usuario dice «una persona camina», no se infiere edad, identidad, vestimenta especial, destino emocional ni motivo.
- Si el proyecto ya tiene un personaje registrado, se usa ese perfil; no se genera otro parecido.

## 2. Selección de perfil

Orden obligatorio:
1. Perfil guardado y aprobado por el usuario para el proyecto.
2. Perfil explícito pedido en el prompt.
3. Perfil recomendado por el tipo de tarea, solo si es necesario y sin contradecir instrucciones.
4. neutral_studio como fallback general cuando no hay contexto suficiente.
5. Si no es posible decidir sin alterar el significado, preguntar o registrar la ambigüedad; no inventar una solución como si fuera un hecho.

La selección registra profile_id, versión, motivo, valores aplicados y origen de cada valor.

## 3. Perfiles iniciales

### neutral_studio — fallback general
- Fondo continuo gris neutro, suelo mate y horizonte visual discreto.
- Iluminación amplia y suave, sin hora del día aparente.
- Sujeto principal solo si el prompt lo solicita o el proyecto ya lo tiene seleccionado.
- Sin utilería, texto, logos, multitudes, clima, decoraciones ni objetos narrativos añadidos.
- Cámara de referencia fija de tres cuartos; vistas frontal, lateral y cenital para inspección.
- Sin movimiento por defecto: pose neutra/idle.
- Escala y origen definidos en el perfil, no inferidos en cada toma.

### greybox_lab — prueba geométrica
- Volumen de prueba simple, suelo y límites visibles opcionales.
- Materiales planos y sin texturas decorativas.
- Objetos de prueba etiquetados por rol e ID.
- Diseñado para colisión, trayectorias, límites y coordenadas, no para apariencia final.

### empty_room — interior solicitado
- Habitación simple, paredes, suelo y techo según configuración explícita.
- Puertas, ventanas y muebles solo cuando se soliciten o formen parte de un estado aprobado.
- Una abertura necesaria para cámara o navegación es una decisión técnica registrada, no un elemento narrativo oculto.
- La habitación actual del laboratorio es un fixture de prueba, no el entorno universal.

### neutral_outdoor — exterior mínimo
- Plano de suelo, fondo/cielo uniforme y luz difusa.
- Sin edificios, vegetación, caminos, montañas, clima ni objetos lejanos salvo petición.
- El plano infinito de prueba no debe presentarse como geografía realista.

## 4. Capas de escena

- world_static: arquitectura y terreno persistentes.
- props_persistent: objetos que siguen existiendo entre tomas.
- characters: sujetos con identidad y estado propios.
- motion_targets: objetivos y marcadores técnicos; invisibles en render final salvo depuración.
- camera_rigs: cámaras y puntos de mira; no son entidades narrativas.
- lighting: luces y control de exposición.
- debug: ejes, cajas, IDs, trayectorias y colisionadores de diagnóstico.
- ephemeral_fx: efectos temporales autorizados por un evento (polvo, chispas, etc.).

Las capas técnicas no deben aparecer en el vídeo final. Las capas de depuración se pueden renderizar en imágenes de diagnóstico, nunca mezclarse silenciosamente con la salida cinematográfica.

## 5. Defaults explícitos frente a hechos

Cada propiedad indica su origen:
- user_explicit: dicho directamente por el usuario.
- project_approved: confirmado previamente para este proyecto.
- template_default: valor de presentación de una plantilla neutra.
- inferred_low_confidence: interpretación necesaria pero incierta.
- system_derived: calculado desde geometría o estado existente.

template_default no puede añadir entidades narrativas. inferred_low_confidence debe marcarse y no puede sobreescribir valores explícitos ni identidad aprobada.

## 6. Cámara y neutralidad

La cámara no modifica el mundo. Cambiar de frontal a lateral no mueve personajes, muebles ni luces físicas. Los encuadres técnicos deben evitar cortar partes importantes del sujeto, mantener escala y lente estables entre referencias comparables, guardar posición/orientación/lente/relación de aspecto/objetivo, distinguir cámara de inspección de cámara cinematográfica y no ocultar colisiones cambiando el ángulo.

## 7. Política de objetos y ausencias

«No especificado» no significa «sí». La escena no añade objetos por plausibilidad. Si un objeto está ausente del estado canónico, el generador no debe recibir una referencia que lo sugiera como parte del mundo.

Si el prompt exige un objeto nuevo, el compilador crea una propuesta con ID estable y ubicación válida. Si no cabe, contradice un límite o requiere una decisión narrativa no indicada, el plan se marca como bloqueado/ambiguo en vez de desplazar otras entidades sin permiso.

## 8. Persistencia y cambios

- Los cambios persistentes crean una nueva versión del estado; no sobrescriben el historial.
- Un objeto oculto por cámara sigue existiendo.
- Un objeto eliminado requiere un evento explícito.
- Cambios de vestimenta, identidad, escala, arquitectura o posición base requieren una acción/edición autorizada y nueva versión.
- Los efectos temporales caducan según evento o duración explícita.
- La memoria solo acepta cambios observados después de validación y con evidencia; un fotograma generado no se convierte automáticamente en verdad del mundo.

## 9. Pruebas de aceptación

1. Mismo perfil, versión y semilla producen el mismo estado estructural.
2. Un prompt mínimo no añade entidades narrativas no solicitadas.
3. Una entidad persistente conserva ID, transformación y perfil al cambiar la cámara.
4. La cámara puede moverse sin alterar transformaciones del mundo.
5. La capa debug no se filtra al render final.
6. Ambigüedades de identidad, acción, ubicación o continuidad quedan registradas.
7. La habitación de prueba no se elige para un prompt exterior ni como entorno universal.
8. Los valores por defecto se distinguen de los hechos confirmados.
9. Si una restricción no se puede verificar, el informe dice unknown/not_verified, no pass.

## 10. Fuera de alcance por ahora

Este documento no implementa selección automática de plantillas, generación de rigs, física completa, segmentación de vídeo ni un adaptador para un generador externo. Define contratos para que esas funciones se implementen sin comportamientos contradictorios.
