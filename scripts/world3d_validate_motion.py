import bpy
import json
import os
from mathutils import Vector

ROOT = os.path.abspath(os.getcwd())
ARTIFACTS = os.path.join(ROOT, "artifacts")
BLEND = os.path.join(ARTIFACTS, "stlat-world3d.blend")
REPORT = os.path.join(ARTIFACTS, "stlat-world3d-motion-validation.json")
ROOM_MIN = Vector((-4.0, -4.0, 0.0))
ROOM_MAX = Vector((4.0, 4.0, 3.2))
SAMPLES = 48
EPSILON = 0.015

if not os.path.isfile(BLEND):
    raise FileNotFoundError("Missing generated world: " + BLEND)
bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
bpy.context.view_layer.update()
depsgraph = bpy.context.evaluated_depsgraph_get()

def bounds(obj):
    evaluated = obj.evaluated_get(depsgraph)
    corners = [evaluated.matrix_world @ Vector(c) for c in evaluated.bound_box]
    return (
        Vector(tuple(min(p[i] for p in corners) for i in range(3))),
        Vector(tuple(max(p[i] for p in corners) for i in range(3))),
    )

def overlaps(a_min, a_max, b_min, b_max):
    return all(a_min[i] < b_max[i] - EPSILON and a_max[i] > b_min[i] + EPSILON for i in range(3))

parts = [o for o in scene.objects if o.type == "MESH" and o.get("stlat_role", "").startswith("character.") and o.get("stlat_role") != "character.anchor"]
if not parts:
    # Compatibility with the current scene, where the anchor is tagged as debug.root_anchor.
    parts = [o for o in scene.objects if o.type == "MESH" and o.get("stlat_role", "").startswith("character.")]
if not parts:
    raise RuntimeError("No character mesh parts found in the saved world")

anchor = next((o for o in scene.objects if o.name == "Character.Anchor"), None)
if anchor is None:
    raise RuntimeError("Character.Anchor missing; cannot derive the authoritative character root")
root = anchor.location - Vector((0.0, -0.22, 0.06))
part_bounds = [(o.name, *bounds(o)) for o in parts]
obstacle_roles = {
    "environment.wall", "prop.bed", "prop.bed_surface", "prop.pillow",
    "prop.table", "prop.table_leg", "prop.window"
}
obstacles = [(o.name, *bounds(o)) for o in scene.objects
             if o.type == "MESH" and o.get("stlat_role") in obstacle_roles]

def evaluate_position(target_root):
    delta = Vector(target_root) - root
    translated = []
    for name, bmin, bmax in part_bounds:
        translated.append((name, bmin + delta, bmax + delta))
    outside = []
    for name, bmin, bmax in translated:
        if any(bmin[i] < ROOM_MIN[i] - EPSILON or bmax[i] > ROOM_MAX[i] + EPSILON for i in range(3)):
            outside.append(name)
    hits = []
    for name, bmin, bmax in translated:
        for obstacle_name, omin, omax in obstacles:
            if overlaps(bmin, bmax, omin, omax):
                hits.append({"part": name, "obstacle": obstacle_name})
    return {"inside_room": not outside, "outside_parts": outside, "collisions": hits}

def sample_path(start, end, samples=SAMPLES):
    path_results = []
    for step in range(samples + 1):
        t = step / samples
        point = [start[i] + (end[i] - start[i]) * t for i in range(3)]
        result = evaluate_position(point)
        if not result["inside_room"] or result["collisions"]:
            path_results.append({
                "sample": step, "t": round(t, 4), "root": [round(v, 4) for v in point],
                "inside_room": result["inside_room"],
                "outside_parts": result["outside_parts"],
                "collisions": result["collisions"][:8],
            })
    return path_results

start = [round(float(v), 4) for v in root]
safe_end = [float(root.x), -2.70, 0.0]
bed_target = [2.45, 1.25, 0.0]
outside_target = [4.55, float(root.y), 0.0]

safe_violations = sample_path(start, safe_end)
bed_path_violations = sample_path(start, bed_target)
outside_result = evaluate_position(outside_target)

checks = {
    "character_parts_found": len(parts) >= 7,
    "safe_path_is_collision_free": len(safe_violations) == 0,
    "bed_path_collision_detected": any(v["collisions"] for v in bed_path_violations),
    "room_boundary_violation_detected": not outside_result["inside_room"],
}
checks["status"] = "success" if all(checks.values()) else "failed"
report = {
    "schema": "stlat.motion-validation.v1",
    "status": checks["status"],
    "method": "sampled world-space AABB collision and room-boundary checks; conservative proxy validation, not a physics simulation",
    "samples_per_path": SAMPLES,
    "epsilon_m": EPSILON,
    "character_root": start,
    "paths": {
        "safe_walk_forward": {
            "start": start, "end": safe_end,
            "violating_samples": len(safe_violations),
            "first_violations": safe_violations[:5],
        },
        "intentionally_blocked_toward_bed": {
            "start": start, "end": bed_target,
            "violating_samples": len(bed_path_violations),
            "first_violations": bed_path_violations[:5],
        },
        "intentionally_outside_room": {
            "target": outside_target,
            "inside_room": outside_result["inside_room"],
            "outside_parts": outside_result["outside_parts"],
        },
    },
    "checks": checks,
    "obstacle_count": len(obstacles),
    "character_part_count": len(parts),
}
with open(REPORT, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)
print("STLAT_MOTION_VALIDATION=" + json.dumps({
    "status": checks["status"], "checks": checks,
    "character_part_count": len(parts), "obstacle_count": len(obstacles),
    "safe_path_violations": len(safe_violations),
    "bed_path_violations": len(bed_path_violations),
    "report": REPORT,
}))
if checks["status"] != "success":
    raise RuntimeError("ST-LAT motion validation failed: " + json.dumps(checks))
