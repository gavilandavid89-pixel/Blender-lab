import bpy
import math
import os
import json
from mathutils import Vector

ROOT = os.path.abspath(os.getcwd())
OUT = os.path.join(ROOT, "artifacts")
os.makedirs(OUT, exist_ok=True)

# Start from a clean scene.
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for datablocks in (bpy.data.materials, bpy.data.cameras, bpy.data.lights):
    for block in list(datablocks):
        if block.users == 0:
            datablocks.remove(block)

def material(name, color, metallic=0.0, roughness=0.38):
    mat = bpy.data.materials.new(name=name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
    return mat

blue = material("Lab Blue", (0.035, 0.24, 0.85), metallic=0.25)
orange = material("Signal Orange", (1.0, 0.19, 0.035), metallic=0.05)
gold = material("Warm Gold", (1.0, 0.58, 0.055), metallic=0.65, roughness=0.24)
ground = material("Matte Graphite", (0.035, 0.045, 0.065), roughness=0.82)

# Ground platform.
bpy.ops.mesh.primitive_plane_add(size=14, location=(0, 0, -0.08))
floor = bpy.context.object
floor.name = "Ground"
floor.data.materials.append(ground)

# Main objects.
bpy.ops.mesh.primitive_cube_add(size=1.65, location=(-1.65, 0, 0.82))
cube = bpy.context.object
cube.name = "Blue Cube"
cube.data.materials.append(blue)
bevel = cube.modifiers.new("Soft machined edges", "BEVEL")
bevel.width = 0.09
bevel.segments = 3
cube.modifiers.new("Weighted corner normals", "WEIGHTED_NORMAL")

bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.88, location=(0.25, 0, 0.88))
sphere = bpy.context.object
sphere.name = "Orange Sphere"
sphere.data.materials.append(orange)
for poly in sphere.data.polygons:
    poly.use_smooth = True

bpy.ops.mesh.primitive_torus_add(major_radius=0.62, minor_radius=0.19, major_segments=48, minor_segments=16, location=(2.05, 0, 0.95), rotation=(math.radians(68), math.radians(12), math.radians(-18)))
torus = bpy.context.object
torus.name = "Gold Torus"
torus.data.materials.append(gold)
for poly in torus.data.polygons:
    poly.use_smooth = True

# Camera.
bpy.ops.object.camera_add(location=(6.5, -10.5, 7.2))
camera = bpy.context.object
camera.name = "Lab Camera"
target = Vector((0.0, 0.0, 0.55))
camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
camera.data.lens = 52
bpy.context.scene.camera = camera

# Large soft lights.
def area_light(name, location, energy, size, color):
    bpy.ops.object.light_add(type="AREA", location=location)
    light = bpy.context.object
    light.name = name
    light.data.energy = energy
    light.data.shape = "DISK"
    light.data.size = size
    light.data.color = color
    light.rotation_euler = (Vector((0, 0, 0.4)) - light.location).to_track_quat("-Z", "Y").to_euler()
    return light

area_light("Key Softbox", (0, -4.5, 7), 1050, 5.0, (0.78, 0.86, 1.0))
area_light("Warm Rim", (3.5, 2.5, 5), 1250, 3.0, (1.0, 0.48, 0.2))
area_light("Fill", (-4, 1, 3.5), 700, 4.0, (0.28, 0.48, 1.0))

scene = bpy.context.scene
# Prefer Eevee Next on newer versions; fall back on older Blender releases.
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 960
scene.render.resolution_y = 540
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.render.filepath = os.path.join(OUT, "blender-lab-preview.png")
scene.render.image_settings.color_mode = "RGBA"
scene.render.resolution_percentage = 100
scene.render.engine = scene.render.engine
scene.render.image_settings.color_depth = "8"
scene.render.use_file_extension = True
scene.render.filepath = os.path.join(OUT, "blender-lab-preview.png")
scene.world.color = (0.025, 0.03, 0.05)
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "Medium High Contrast"
scene.camera.data.dof.use_dof = False

# Select the three showcase objects for a useful opening view in Blender.
bpy.ops.object.select_all(action="DESELECT")
for obj in (cube, sphere, torus):
    obj.select_set(True)
bpy.context.view_layer.objects.active = cube

blend_path = os.path.join(OUT, "blender-lab-scene.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print("BLENDER_LAB: scene saved:", blend_path)
print("BLENDER_LAB: rendering preview:", scene.render.filepath)
bpy.ops.render.render(write_still=True)

summary = {
    "status": "success",
    "blender_version": bpy.app.version_string,
    "objects": [obj.name for obj in scene.objects],
    "blend_file": blend_path,
    "render_file": scene.render.filepath,
    "resolution": [scene.render.resolution_x, scene.render.resolution_y],
}
with open(os.path.join(OUT, "scene-summary.json"), "w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2)
print("BLENDER_LAB: finished successfully")
