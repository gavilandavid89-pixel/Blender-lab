"""Exercise real camera operations in the saved Blender scene and prove world invariance."""
import bpy
import hashlib
import json
import math
import os
from mathutils import Vector

ROOT = os.path.abspath(os.getcwd())
ARTIFACTS = os.path.join(ROOT, "artifacts")
REPORT = os.path.join(ARTIFACTS, "stlat-world3d-camera-isolation.json")
os.makedirs(ARTIFACTS, exist_ok=True)

scene = bpy.context.scene
bpy.context.view_layer.update()

def rounded(values, digits=6):
    return [round(float(v), digits) for v in values]

def object_signature(obj):
    """Capture transforms, dimensions and evaluated world-space mesh geometry."""
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    matrix = [round(float(v), 7) for row in evaluated.matrix_world for v in row]
    dimensions = rounded(evaluated.dimensions, 7)
    geometry_hash = None
    vertex_count = 0
    if obj.type == "MESH":
        mesh = evaluated.to_mesh()
        try:
            coords = []
            for vertex in mesh.vertices:
                world = evaluated.matrix_world @ vertex.co
                coords.extend(round(float(v), 6) for v in world)
            vertex_count = len(mesh.vertices)
            geometry_hash = hashlib.sha256(
                json.dumps(coords, separators=(",", ":"), allow_nan=False).encode("utf-8")
            ).hexdigest()
        finally:
            evaluated.to_mesh_clear()
    payload = {
        "id": obj.get("stlat_id", obj.name),
        "name": obj.name,
        "type": obj.type,
        "role": obj.get("stlat_role", "unclassified"),
        "matrix_world": matrix,
        "dimensions": dimensions,
        "vertex_count": vertex_count,
        "geometry_sha256_world_vertices": geometry_hash,
    }
    return payload

def world_snapshot():
    return {
        obj.name: object_signature(obj)
        for obj in sorted(scene.objects, key=lambda item: item.name)
        if obj.type != "CAMERA"
    }

main = scene.objects.get("Camera.Main")
top = scene.objects.get("Camera.Top")
if main is None or main.type != "CAMERA":
    raise RuntimeError("Required camera Camera.Main is missing")
if top is None or top.type != "CAMERA":
    raise RuntimeError("Required camera Camera.Top is missing")

before_world = world_snapshot()
before_main = {
    "location": rounded(main.location),
    "rotation_euler": rounded(main.rotation_euler),
    "lens": round(float(main.data.lens), 5),
}
before_top = {
    "location": rounded(top.location),
    "rotation_euler": rounded(top.rotation_euler),
    "lens": round(float(top.data.lens), 5),
}
initial_active_camera = scene.camera.name if scene.camera else None

# Exercise actual Blender camera operations: select another camera, move/rotate
# the main camera, change its lens, and activate the top camera. Do not save.
scene.camera = top
main.location.x += 0.37
main.location.y -= 0.21
main.rotation_euler.z += 0.08
main.data.lens = float(main.data.lens) + 7.0
bpy.context.view_layer.update()
scene.camera = main
bpy.context.view_layer.update()
scene.camera = top
bpy.context.view_layer.update()

after_world = world_snapshot()
after_main = {
    "location": rounded(main.location),
    "rotation_euler": rounded(main.rotation_euler),
    "lens": round(float(main.data.lens), 5),
}
after_top = {
    "location": rounded(top.location),
    "rotation_euler": rounded(top.rotation_euler),
    "lens": round(float(top.data.lens), 5),
}
changed_world_objects = [
    name for name in sorted(set(before_world) | set(after_world))
    if before_world.get(name) != after_world.get(name)
]
camera_operation_changed = before_main != after_main
active_camera_is_top = scene.camera is top
checks = {
    "required_cameras_found": True,
    "camera_transform_or_lens_changed": camera_operation_changed,
    "active_camera_switch_applied": active_camera_is_top,
    "non_camera_objects_unchanged": len(changed_world_objects) == 0,
    "non_camera_geometry_and_transforms_unchanged": len(changed_world_objects) == 0,
}
checks["status"] = "success" if all(value for key, value in checks.items() if isinstance(value, bool)) else "failed"
report = {
    "schema": "stlat.camera-isolation.v1",
    "status": checks["status"],
    "method": "saved Blender scene; mutate camera transform and lens, switch active camera, compare non-camera world transforms, dimensions and evaluated world-space mesh vertex hashes",
    "scene_file": "artifacts/stlat-world3d.blend",
    "initial_active_camera": initial_active_camera,
    "final_active_camera": scene.camera.name if scene.camera else None,
    "camera_before": {"Camera.Main": before_main, "Camera.Top": before_top},
    "camera_after": {"Camera.Main": after_main, "Camera.Top": after_top},
    "non_camera_object_count": len(before_world),
    "mesh_geometry_count": sum(1 for item in before_world.values() if item["type"] == "MESH"),
    "changed_non_camera_objects": changed_world_objects,
    "checks": checks,
    "note": "The modified scene is not saved; this test proves camera operations in this run do not mutate the captured non-camera scene state. It does not prove invariance for arbitrary third-party scripts.",
}
with open(REPORT, "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, allow_nan=False)
print("STLAT_CAMERA_ISOLATION=" + json.dumps({
    "status": checks["status"],
    "checks": checks,
    "non_camera_object_count": len(before_world),
    "mesh_geometry_count": report["mesh_geometry_count"],
    "changed_non_camera_objects": changed_world_objects,
    "report": REPORT,
}))
if checks["status"] != "success":
    raise RuntimeError("ST-LAT camera isolation failed: " + json.dumps(checks))
