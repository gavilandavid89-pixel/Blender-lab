# ST-LAT World3D Lab 🧪

Laboratorio privado para probar el mundo 3D controlado de ST-LAT Engine desde Ubuntu remoto, sin necesitar un PC ni instalar Blender en el móvil.

## Objetivo de esta prueba

Antes de conectar un generador de vídeo, necesitamos una escena 3D reproducible que actúe como fuente de verdad. Esta prueba crea una habitación, objetos con IDs/roles estables y un personaje proxy segmentado. Exporta geometría aproximada, coordenadas y referencias visuales para que los siguientes módulos puedan verificar continuidad espacial.

## Qué genera

- `stlat-world3d.blend`: escena editable.
- `stlat-world3d-main.png`: vista principal.
- `stlat-world3d-topdown.png`: vista cenital para comprobar la distribución espacial.
- `stlat-world3d-manifest.json`: contrato del mundo, ejes, unidades, roles, transformaciones, AABB y validaciones.
- `blender.log`: registro completo de la ejecución.

## Contrato espacial inicial

- Unidades: metros.
- Ejes: X = derecha, Y = profundidad (positivo hacia la pared del fondo), Z = arriba.
- La habitación define un volumen interior conocido.
- Los objetos tienen un rol semántico y un ID estable.
- El personaje actual es un proxy geométrico, no un rig final ni un modelo generado por IA.

## Ejecución

Los cambios en `scripts/**`, este README o el workflow activan GitHub Actions. También se puede iniciar manualmente desde **Actions → Blender Headless Lab → Run workflow**.

Los resultados aparecen como el artefacto `blender-lab-output` en la ejecución correspondiente.

## Qué todavía NO está resuelto

Esto valida la construcción determinista del mundo y algunos invariantes básicos. Aún no valida colisiones físicas completas, animación/esqueleto, persistencia entre tomas, generación de vídeo ni fidelidad de identidad. Esos son pasos posteriores; no deben darse por implementados solo porque el render funcione.
