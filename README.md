# ST-LAT World3D Lab 🧪

Laboratorio de ingeniería para validar el **mundo 3D controlado de ST-LAT Engine** usando Blender en modo headless y GitHub Actions. El entorno de pruebas permite avanzar sin instalar Blender en un teléfono ni depender de una interfaz gráfica.

> **Principio central:** el estado canónico del mundo es la fuente de verdad. Una escena renderizada o un vídeo generado son representaciones que deben contrastarse con ese estado; no pueden redefinirlo silenciosamente.

## Índice

- [Objetivo y alcance](#objetivo-y-alcance)
- [Arquitectura actual](#arquitectura-actual)
- [Flujo de datos validado](#flujo-de-datos-validado)
- [Artefactos](#artefactos)
- [Contrato espacial](#contrato-espacial)
- [Ejecutar comprobaciones](#ejecutar-comprobaciones)
- [CI y resultados](#ci-y-resultados)
- [Estado real y límites conocidos](#estado-real-y-límites-conocidos)
- [Próximos hitos](#próximos-hitos)
- [Documentación técnica](#documentación-técnica)

## Objetivo y alcance

ST-LAT está diseñado para ayudar a que un futuro sistema de generación de vídeo respete continuidad espacial y temporal: identidad, posición, escala, objetos presentes, trayectorias, relaciones y cámara.

Este repositorio valida primero los mecanismos del mundo 3D. **Todavía no es un generador de vídeo conectado a una IA.** No se afirma que el motor pueda eliminar todas las alucinaciones; se busca convertir requisitos importantes en restricciones explícitas, comprobarlas y producir evidencia reproducible.

## Arquitectura actual

| Componente | Responsabilidad | Estado comprobado en el código |
|---|---|---|
| Manifiesto World3D | Describe entidades, roles, transformaciones, dimensiones, AABB, ejes y unidades | Implementado para la escena de laboratorio y validado por script |
| Constructor Blender | Crea la habitación de prueba, el personaje proxy, cámaras y renders | Implementado en modo headless |
| Validador espacial | Comprueba límites y trayectorias mediante AABB y muestreo | Implementación inicial; no es física continua |
| Determinismo | Compara dos construcciones independientes, IDs y datos geométricos canonizados | Script y paso CI dedicados |
| Aislamiento de cámara | Cambia cámara/lente en la escena guardada y comprueba que las entidades no cámara no cambien | Script y paso CI dedicados |
| Contrato del estado del mundo | Valida entidades, transformaciones, versiones, jerarquías y transiciones | Prototipo Python con regresiones |
| Replay de eventos | Reconstruye estado a partir de eventos aprobados y rechaza transiciones contradictorias | Implementado para los casos cubiertos por pruebas |
| Almacén de snapshots | Persiste versiones locales, comprueba linaje/integridad y permite recargar versiones; prueba de regresión con varios personajes, un animal y un objeto a través de v1–v5 | Prototipo local de un solo escritor; la prueba multi-entidad valida persistencia JSON, no continuidad visual en vídeo |
| Puente de sincronización con Blender | Aplica snapshots a varias mallas existentes en una operación y verifica transforms, AABB, colisiones y rollback | Integración inicial; prueba torso+cabeza, aún limitada a mallas sin padre y sin creación/eliminación |
| Compilador de prompt / adaptador de vídeo / evaluador temporal | Traduce instrucciones y compara vídeo candidato con el mundo | Diseño pendiente de implementación |

Los estados de la tabla son deliberadamente conservadores: que exista un contrato de diseño no significa que ese módulo esté implementado. La matriz de pruebas identifica qué comportamiento se ha comprobado y qué límites conserva.

## Flujo de datos validado

El laboratorio está construyendo y probando la siguiente cadena:

1. Definir y validar un estado del mundo.
2. Proponer un evento explícito y aprobado.
3. Validar la transición y producir una nueva versión.
4. Guardar snapshots versionados en el almacén local.
5. Recargar la versión guardada y reproducir eventos para comprobar equivalencia canónica.
6. Aplicar el estado recuperado a una malla compatible de Blender.
7. Verificar la transformación y su AABB evaluada, preservar objetos no objetivo y rechazar operaciones inválidas.
8. Rechazar movimientos cuya trayectoria muestreada cruce un obstáculo, incluso si la pose final está libre.
9. Guardar informes JSON y el registro de ejecución como evidencia.

La regresión multi-entidad crea un segundo personaje, un perro y una pelota mediante eventos aprobados, guarda versiones sucesivas y verifica que sus IDs, referencias de identidad y transforms siguen presentes al recargar el mundo. Esto valida persistencia estructurada entre estados; aún no prueba que un generador de vídeo mantenga esas identidades visualmente.

La autoprueba de Blender también aplica un snapshot con dos entidades existentes (torso y cabeza), verifica que ambas se aplican y que las demás mallas permanecen intactas. Esto amplía la sincronización multi-entidad, pero no implementa todavía creación/eliminación de objetos ni identidad visual en vídeo.

La integración actual **no** es una base de datos multiusuario ni un servicio de sincronización continuo. El puente de Blender no crea/elimina/reparenta entidades, no sincroniza rigs, cámaras, luces o animación, y no guarda automáticamente la escena modificada.

## Artefactos

La acción publica el artefacto `stlat-world3d-output`, que puede contener:

- `stlat-world3d.blend`: escena editable de Blender.
- `stlat-world3d-main.png`: render de referencia principal.
- `stlat-world3d-topdown.png`: vista cenital.
- `stlat-world3d-manifest.json`: contrato espacial del mundo.
- `stlat-world3d-motion-validation.json`: resultados de pruebas de movimiento y límites.
- `stlat-world3d-camera-isolation.json`: evidencia de aislamiento de cámara.
- `stlat-world3d-determinism.json`: comparación de construcciones independientes.
- `stlat-world-state-replay.json`: informe de reproducción de eventos.
- `stlat-world-state-store.json`: informe de persistencia, versiones e integridad.
- `stlat-world-state-blender-sync.json`: evidencia de la integración inicial entre persistencia y Blender.
- `blender.log`: salida de Blender y diagnósticos de la ejecución.

Los artefactos pertenecen a una ejecución concreta. Para saber qué commit probaron y si terminaron correctamente, abre esa ejecución en Actions; no infieras que un cambio reciente pasó porque una ejecución histórica estuviera verde.

## Contrato espacial

- Unidades: metros.
- Ejes: X = derecha, Y = profundidad (positivo hacia la pared del fondo), Z = arriba.
- Habitación interior de prueba: X/Y entre -4 y 4; Z entre 0 y 3.2.
- Las entidades físicas deben respetar los límites duros del mundo; las cámaras pueden situarse fuera de ellos.
- Cada entidad usa un ID estable y un rol semántico. Los `parent_id` deben apuntar a entidades existentes y no pueden formar ciclos.
- Cambiar la relación padre-hijo requiere una transición aprobada.
- El personaje actual es un **proxy geométrico segmentado**, no un rig final ni una identidad visual persistente.

### Movimiento y colisiones

El validador de movimiento prueba un recorrido seguro, una trayectoria dirigida deliberadamente hacia la cama y una posición fuera de los límites. El puente de sincronización también prueba una trayectoria sólida que cruza la cama aunque su punto final esté libre.

Las comprobaciones actuales usan AABB y muestras de trayectoria. El muestreo de la integración Blender usa intervalos de hasta 0,1 unidades con un máximo de 256 muestras en el caso cubierto por la prueba. Esto es una defensa práctica, no una garantía matemática contra cualquier colisión entre muestras ni un solver de física continua. Las mallas rotadas, deformables y las articulaciones necesitan validación más precisa.

## Primera conexión de IA (opcional)

El adaptador inicial `scripts/ai_world_planner.py` usa la API compatible con OpenAI de Groq y el modelo `openai/gpt-oss-20b` por defecto. La IA recibe una versión resumida del snapshot y devuelve una **propuesta JSON**, no ejecuta Blender ni modifica el estado canónico. En esta primera fase solo puede proponer transformaciones para IDs existentes; no puede crear/eliminar entidades ni cambiar identidades.

La validación local no necesita API ni paquetes externos:

```bash
python3 -m unittest tests.test_ai_world_planner -v
```

Para una prueba real, crea una API key desde la consola de Groq y guárdala como variable de entorno `GROQ_API_KEY`; nunca la pegues en el código ni la subas al repositorio. En GitHub, añádela como **Settings → Secrets and variables → Actions → New repository secret**, con nombre exacto `GROQ_API_KEY`. Después ejecuta **Actions → Blender Headless Lab → Run workflow**. Si el secreto no está configurado, el paso de IA se omite sin impedir las pruebas de Blender. Si está configurado, el workflow realiza una petición real y guarda `artifacts/ai-world-plan.json`.

La API gratuita de Groq no usa un saldo de créditos prepago, pero **sí tiene límites de solicitudes y tokens**; no es uso ilimitado. Consulta los [límites oficiales de Groq](https://console.groq.com/docs/rate-limits). Si se alcanza una cuota, la petición puede devolver HTTP 429. El proveedor y el modelo son configurables mediante `STLAT_AI_ENDPOINT` y `STLAT_AI_MODEL`.

## Ejecutar comprobaciones

### Pruebas rápidas (sin Blender)

Desde la raíz del repositorio, con Python 3:

```bash
python3 scripts/validate_scene_profiles.py
python3 scripts/validate_world_manifest.py --self-test
python3 -m unittest discover -s tests -v
python3 scripts/validate_motion_report.py --self-test
python3 scripts/validate_world_replay.py
python3 scripts/validate_world_store.py
python3 scripts/validate_deterministic_manifest.py --self-test
python3 scripts/validate_camera_isolation_report.py --self-test
```

Los scripts de autoprueba generan o verifican evidencia temporal en `artifacts/` según su implementación. Algunos validadores también aceptan una ruta de informe para validar resultados producidos previamente; consulta el propio script y la [guía de CI](docs/CI_AND_ARTIFACTS.md) antes de ejecutar modos distintos de `--self-test`.

### Integración real con Blender

El flujo completo está automatizado en GitHub Actions. Para ejecutarlo:

1. Abre la pestaña [Actions](../../actions).
2. Selecciona **Blender Headless Lab**.
3. Usa **Run workflow** para lanzar una ejecución manual, o realiza un push a `main` que cambie archivos cubiertos por el workflow.
4. Abre la ejecución nueva y comprueba el resultado del job, no solo que la acción haya comenzado.
5. Descarga `stlat-world3d-output` y revisa los JSON y `blender.log`.

El workflow instala Blender 5.2.2 en Ubuntu, ejecuta validaciones de contrato, construye la escena sin interfaz gráfica, valida movimiento, compara un segundo build determinista, prueba aislamiento de cámara y sincronización de estado, valida informes y publica artefactos. El job tiene un límite de ejecución configurado; un timeout o fallo de infraestructura debe distinguirse de una regresión de código.

## CI y resultados

- Workflow: [Blender Headless Lab](.github/workflows/blender.yml).
- Historial: [ejecuciones de Actions](../../actions/workflows/blender.yml).
- Las pruebas de contrato y las pruebas de Blender son capas distintas: un conjunto unitario verde no demuestra por sí solo que el render y la integración de Blender hayan pasado.
- Para considerar verificada una capacidad, debe existir evidencia relevante, pruebas positivas y negativas cuando corresponda y una ejecución completa exitosa sobre el commit que contiene la implementación.
- La matriz de pruebas registra el alcance de cada caso y las capacidades pendientes: [docs/TEST_MATRIX.md](docs/TEST_MATRIX.md).

## Estado real y límites conocidos

### Implementado parcialmente / con pruebas específicas

- Habitación de laboratorio, personaje proxy, cámaras, manifiesto y renders.
- Validación del manifiesto y de perfiles de escena.
- Pruebas de movimiento mediante AABB muestreada.
- Comparación determinista de IDs, transformaciones y hashes canonizados de geometría.
- Prueba de aislamiento de cámara sobre una escena guardada.
- Contratos de estado versionado, transiciones aprobadas y jerarquías.
- Replay de eventos y almacenamiento local de snapshots inmutables.
- Prueba inicial de la cadena snapshot persistido → recarga/replay → aplicación a Blender → validación/rollback.

### Pendiente antes de conectar un generador de vídeo

- Registro persistente de identidades y assets a través de cambios intencionales entre sesiones.
- Compilador de instrucciones en lenguaje natural que convierta prompts en planes estructurados sin añadir hechos no solicitados.
- Aplicación completa de creación, eliminación, jerarquía y transformaciones a toda la escena.
- Almacén duradero independiente para eventos, concurrencia y persistencia multiusuario.
- Colisiones con volúmenes más precisos, articulación/rig y navegación de varias etapas.
- Generación de referencias por fotograma (profundidad, silueta, máscaras por entidad, pose y parámetros de cámara).
- Adaptador para un generador de vídeo concreto con capacidades declaradas.
- Evaluador temporal de identidad, posición, presencia de objetos, oclusiones y continuidad.
- Reparación y reintentos limitados que nunca relajen restricciones para hacer pasar un resultado inválido.

La IA de vídeo no está conectada todavía. No se deben presentar las capacidades pendientes como funcionalidades disponibles.

## Próximos hitos

1. **Mantener CI verde:** ejecutar el workflow completo después de cada cambio relevante y actualizar la matriz con evidencia del commit actual.
2. **Endurecer el puente de estado:** ampliar pruebas de rollback, entidades múltiples y cambios de jerarquía; conservar la invariancia de objetos no objetivo.
3. **Mejorar el movimiento:** comparar el muestreo AABB con volúmenes de colisión más precisos y probar trayectorias rápidas/estrechas.
4. **Persistencia y procedencia:** separar eventos duraderos del almacén de snapshots y registrar origen/prioridad de valores explícitos, aprobados, por defecto o desconocidos.
5. **Preparar la interfaz de IA:** diseñar un contrato de plan estructurado y referencias por fotograma, sin conectar un proveedor hasta que el mundo y sus invariantes sean verificables.

Cada hito debe terminar con código, pruebas, documentación y evidencia reproducible. Si una prueba no existe o no se ejecutó, el estado debe permanecer como pendiente/no verificado.

## Documentación técnica

- [Arquitectura funcional y módulos M00–M13](docs/STLAT_ENGINE_SPEC.md)
- [Contratos operativos de módulos M00–M16](docs/SCENE_AND_MODULE_CONTRACTS.md)
- [Reglas de escenas neutras y valores por defecto](docs/NEUTRAL_SCENES.md)
- [Esquema JSON de perfiles de escena](docs/schemas/scene-profile.v1.schema.json)
- [Perfil de ejemplo neutral_studio](docs/examples/neutral-studio.v1.json)
- [Esquema del estado persistente del mundo](docs/schemas/world-state.v1.schema.json)
- [Matriz de pruebas, evidencia y capacidades pendientes](docs/TEST_MATRIX.md)
- [Contrato ejecutable de snapshots y transiciones](scripts/world_state_contract.py)
- [Guía de CI, artefactos y diagnóstico de fallos](docs/CI_AND_ARTIFACTS.md)

---

**Regla de ingeniería:** no marcar una capacidad como implementada solo porque esté documentada o porque exista un archivo con ese nombre. El estado se determina por el código ejecutable, las pruebas pertinentes y la evidencia de una ejecución reproducible.
