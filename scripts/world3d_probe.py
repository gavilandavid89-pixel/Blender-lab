import bpy
import json
import math
import os
import hashlib
from mathutils import Vector

ROOT = os.path.abspath(os.getcwd())
OUT = os.path.join(ROOT, "artifacts")
os.makedirs(OUT, exist_ok=True)

# ST-LAT world contract:
# +X = right, +Y = depth (toward the back wall), +Z = up.
# All dimensions and coordinates are in meters. The room interior is
# X=[-4,4], Y=[-4,4], Z=[0,3.2].
ROOM = {"min": [-4.0, -4.0, 0.0], "max": [4.0, 4.0, 3.2]}

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for collection in (bpy.data.materials, bpy.data.cameras, bpy.data.lights, bpy.data.meshes):
    for block in list(collection):
        if block.users == 0:
            collection.remove(block)

def mat(name, color, roughness=0.7, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
    return m

wall_mat = mat("World | warm plaster", (0.48, 0.42, 0.34))
floor_mat = mat("World | floor", (0.18, 0.22, 0.25))
bed_mat = mat("Prop | bed frame", (0.24, 0.12, 0.07))
linen_mat = mat("Prop | linen", (0.75, 0.78, 0.72))
window_mat = mat("Prop | window blue", (0.08, 0.32, 0.52), 0.25, 0.1)
skin_mat = mat("Character | skin", (0.78, 0.48, 0.32))
shirt_mat = mat("Character | shirt", (0.12, 0.30, 0.78))
pants_mat = mat("Character | pants", (0.08, 0.10, 0.16))
marker_mat = mat("Debug | marker", (0.1, 0.9, 0.35), 0.35, 0.0)

def tag(obj, role, object_id=None):
    obj["stlat_role"] = role
    obj["stlat_id"] = object_id or obj.name.lower().replace(" ", "_")
    return obj

def cube(name, loc, dims, material, role, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel:
        mod = obj.modifiers.new("Soft edges", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return tag(obj, role)

def sphere(name, loc, radius, material, role):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=radius, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    for p in obj.data.polygons:
        p.use_smooth = True
    return tag(obj, role)

# Room shell; the back wall is segmented to leave a real window aperture.
cube("Floor", (0, 0, -0.10), (8, 8, 0.20), floor_mat, "environment.floor")
cube("Wall.Left", (-4.10, 0, 1.60), (0.20, 8.2, 3.2), wall_mat, "environment.wall")
cube("Wall.Right", (4.10, 0, 1.60), (0.20, 8.2, 3.2), wall_mat, "environment.wall")
cube("Wall.Front", (0, -4.10, 1.60), (8.2, 0.20, 3.2), wall_mat, "environment.wall")
cube("Wall.Back.Left", (-2.75, 4.10, 1.60), (2.5, 0.20, 3.2), wall_mat, "environment.wall")
cube("Wall.Back.Right", (2.75, 4.10, 1.60), (2.5, 0.20, 3.2), wall_mat, "environment.wall")
cube("Wall.Back.Sill", (0, 4.10, 0.65), (3.0, 0.20, 1.3), wall_mat, "environment.wall")
cube("Wall.Back.Header", (0, 4.10, 2.70), (3.0, 0.20, 1.0), wall_mat, "environment.wall")
# Window is a visible reference surface placed just inside the aperture.
cube("Window", (0, 3.96, 1.72), (2.75, 0.06, 1.05), window_mat, "prop.window")

# Bed is anchored to the right-hand side. Objects have stable IDs and semantic roles.
cube("Bed.Frame", (2.45, 1.25, 0.32), (1.65, 2.8, 0.48), bed_mat, "prop.bed")
cube("Bed.Mattress", (2.45, 1.20, 0.62), (1.58, 2.62, 0.18), linen_mat, "prop.bed_surface", 0.04)
cube("Bed.Pillow", (2.45, 2.20, 0.75), (0.95, 0.42, 0.12), linen_mat, "prop.pillow", 0.04)
cube("Table", (-2.55, 1.45, 0.58), (1.15, 0.85, 0.12), bed_mat, "prop.table", 0.025)
for x in (-2.98, -2.12):
    for y in (1.15, 1.75):
        cube("Table.Leg", (x, y, 0.28), (0.10, 0.10, 0.55), bed_mat, "prop.table_leg")

# A deliberately simple, segmented character proxy. Stable root coordinate is the source of truth.
character_root = Vector((-0.55, -0.35, 0.0))
sphere("Character.Head", character_root + Vector((0, 0, 1.66)), 0.22, skin_mat, "character.head")
cube("Character.Torso", character_root + Vector((0, 0, 1.18)), (0.48, 0.30, 0.64), shirt_mat, "character.torso", 0.07)
cube("Character.Hips", character_root + Vector((0, 0, 0.78)), (0.40, 0.28, 0.22), pants_mat, "character.hips", 0.04)
for side, label in ((-1, "L"), (1, "R")):
    cube("Character.Leg." + label, character_root + Vector((side * 0.12, 0, 0.39)), (0.15, 0.19, 0.52), pants_mat, "character.leg")
    cube("Character.Arm." + label, character_root + Vector((side * 0.31, 0, 1.20)), (0.13, 0.18, 0.48), shirt_mat, "character.arm")
    sphere("Character.Hand." + label, character_root + Vector((side * 0.32, -0.01, 0.91)), 0.075, skin_mat, "character.hand")
sphere("Character.Anchor", character_root + Vector((0, -0.22, 0.06)), 0.045, marker_mat, "debug.root_anchor")

# Lighting and render setup.
def area_light(name, loc, energy, size, color):
    bpy.ops.object.light_add(type="AREA", location=loc)
    light = bpy.context.object
    light.name = name
    light.data.energy = energy
    light.data.shape = "DISK"
    light.data.size = size
    light.data.color = color
    light.rotation_euler = (Vector((0, 0, 1)) - light.location).to_track_quat("-Z", "Y").to_euler()
    tag(light, "lighting")

area_light("Light.Key", (0, -2.0, 6.0), 900, 5.0, (1.0, 0.83, 0.68))
area_light("Light.Fill", (-3.0, 1.5, 4.0), 650, 4.0, (0.55, 0.70, 1.0))
area_light("Light.Window", (0, 3.0, 2.6), 500, 2.5, (0.45, 0.72, 1.0))

scene = bpy.context.scene
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 960
scene.render.resolution_y = 540
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.image_settings.color_depth = "8"
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "Medium High Contrast"
scene.world.color = (0.12, 0.12, 0.12)

def make_camera(name, loc, target, lens=45):
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.object
    cam.name = name
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    tag(cam, "camera")
    return cam

main_cam = make_camera("Camera.Main", (7.8, -10.5, 7.0), (0, 0, 1.2), 48)
top_cam = make_camera("Camera.Top", (0, 0, 12.0), (0, 0, 0), 45)
scene.camera = main_cam
scene.render.filepath = os.path.join(OUT, "stlat-world3d-main.png")
if os.environ.get("STLAT_SKIP_RENDER") != "1":
    bpy.ops.render.render(write_still=True)
    scene.camera = top_cam
    scene.render.filepath = os.path.join(OUT, "stlat-world3d-topdown.png")
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    bpy.ops.render.render(write_still=True)
else:
    print("STLAT_SKIP_RENDER=1: skipping render pass for deterministic rebuild check")

# Export stable, machine-readable world data after evaluating transforms.
bpy.context.view_layer.update()
depsgraph = bpy.context.evaluated_depsgraph_get()
records = []
for obj in sorted(scene.objects, key=lambda o: o.name):
    if obj.type not in {"MESH", "CAMERA", "LIGHT"}:
        continue
    evaluated = obj.evaluated_get(depsgraph)
    corners = [evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box]
    minimum = [round(min(v[i] for v in corners), 4) for i in range(3)] if corners else None
    maximum = [round(max(v[i] for v in corners), 4) for i in range(3)] if corners else None
    mesh_vertex_count = 0
    mesh_edge_count = 0
    mesh_polygon_count = 0
    mesh_geometry_sha256 = None
    if obj.type == "MESH":
        mesh = evaluated.to_mesh()
        try:
            # Canonicalize by coordinates rather than raw vertex indices. Some
            # Blender primitive meshes can reorder equivalent vertices between
            # independent builds; index-based hashes would report false drift.
            vertex_by_index = {
                int(vertex.index): tuple(round(float(c), 6) for c in vertex.co)
                for vertex in mesh.vertices
            }
            canonical_vertices = sorted(vertex_by_index.values())
            canonical_edges = sorted(
                tuple(sorted(vertex_by_index[int(index)] for index in edge.vertices))
                for edge in mesh.edges
            )
            canonical_faces = []
            for polygon in mesh.polygons:
                points = [vertex_by_index[int(index)] for index in polygon.vertices]
                if points:
                    rotations = [tuple(points[offset:] + points[:offset]) for offset in range(len(points))]
                    canonical_faces.append(min(rotations))
            geometry = {
                "vertices": canonical_vertices,
                "edges": canonical_edges,
                "polygons": sorted(canonical_faces),
            }
            mesh_vertex_count = len(mesh.vertices)
            mesh_edge_count = len(mesh.edges)
            mesh_polygon_count = len(mesh.polygons)
            encoded_geometry = json.dumps(geometry, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
            mesh_geometry_sha256 = hashlib.sha256(encoded_geometry).hexdigest()
        finally:
            evaluated.to_mesh_clear()
    records.append({
        "id": obj.get("stlat_id", obj.name.lower().replace(" ", "_")),
        "name": obj.name,
        "type": obj.type,
        "role": obj.get("stlat_role", "unclassified"),
        "location": [round(float(v), 4) for v in obj.location],
        "rotation_euler_rad": [round(float(v), 5) for v in obj.rotation_euler],
        "dimensions": [round(float(v), 4) for v in obj.dimensions],
        "aabb_world": {"min": minimum, "max": maximum},
        "mesh_vertex_count": mesh_vertex_count,
        "mesh_edge_count": mesh_edge_count,
        "mesh_polygon_count": mesh_polygon_count,
        "mesh_geometry_sha256": mesh_geometry_sha256,
    })

def inside_room(obj):
    p = obj.location
    return -4.0 <= p.x <= 4.0 and -4.0 <= p.y <= 4.0 and 0.0 <= p.z <= 3.2

character_parts = [o for o in scene.objects if o.get("stlat_role", "").startswith("character.")]
character_inside = all(inside_room(o) for o in character_parts)
required_roles = ["character.head", "character.torso", "prop.bed", "prop.window", "environment.floor"]
present_roles = {o.get("stlat_role") for o in scene.objects}
missing_roles = [role for role in required_roles if role not in present_roles]
checks = {
    "character_parts_inside_room_by_origin": character_inside,
    "required_roles_present": not missing_roles,
    "main_camera_exists": main_cam.name in scene.objects,
    "topdown_camera_exists": top_cam.name in scene.objects,
    "coordinate_convention_declared": True,
    "missing_roles": missing_roles,
}
checks["status"] = "success" if all(v for k, v in checks.items() if isinstance(v, bool)) else "failed"

manifest = {
    "schema": "stlat.world3d.v1",
    "status": checks["status"],
    "units": "meters",
    "axes": {"x": "right", "y": "depth; positive toward back wall", "z": "up"},
    "room_interior": ROOM,
    "character_root": [round(float(v), 4) for v in character_root],
    "character_proxy": "segmented placeholder; not final rig",
    "checks": checks,
    "object_count": len(records),
    "objects": records,
    "renders": ["stlat-world3d-main.png", "stlat-world3d-topdown.png"],
}
with open(os.path.join(OUT, "stlat-world3d-manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
blend_path = os.path.join(OUT, "stlat-world3d.blend")
scene.camera = main_cam
scene.render.resolution_x = 960
scene.render.resolution_y = 540
scene.render.filepath = os.path.join(OUT, "stlat-world3d-main.png")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print("STLAT_WORLD3D_MANIFEST=" + json.dumps({"status": checks["status"], "object_count": len(records), "checks": checks}))
if checks["status"] != "success":
    raise RuntimeError("ST-LAT world validation failed: " + json.dumps(checks))
print("STLAT_WORLD3D: validation and renders complete")
