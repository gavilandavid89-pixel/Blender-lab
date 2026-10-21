#!/usr/bin/env python3
"""Render a short, verifiable MP4 from the ST-LAT Blender scene.

This is a pipeline smoke test, not a claim that a video diffusion model is connected.
The deterministic motion is deliberately simple; a later stage will replace the motion
fixture with a validated AI plan while keeping the same rendering and verification path.
Run with Blender opening artifacts/stlat-world3d.blend before this script.
"""
import json
from pathlib import Path
import bpy

ROOT = Path.cwd()
OUT = ROOT / "artifacts"
OUT.mkdir(parents=True, exist_ok=True)
VIDEO = OUT / "stlat-video-smoke.mp4"
REPORT = OUT / "stlat-video-smoke.json"

scene = bpy.context.scene
character_parts = [
    obj for obj in scene.objects
    if obj.type == "MESH" and str(obj.get("stlat_role", "")).startswith("character.")
]
if len(character_parts) < 5:
    raise RuntimeError(f"Expected at least 5 tagged character mesh parts; found {len(character_parts)}")

original_locations = {obj.name: obj.location.copy() for obj in character_parts}
scene.frame_start = 1
scene.frame_end = 49
scene.render.fps = 24
scene.render.fps_base = 1.0
scene.render.resolution_x = 640
scene.render.resolution_y = 360
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "FFMPEG"
scene.render.ffmpeg.format = "MPEG4"
scene.render.ffmpeg.codec = "H264"
scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
scene.render.filepath = str(VIDEO)
scene.render.use_file_extension = True

for obj in character_parts:
    base = original_locations[obj.name]
    for frame, dx in ((1, 0.0), (25, 0.65), (49, 0.0)):
        scene.frame_set(frame)
        obj.location = (base.x + dx, base.y, base.z)
        obj.keyframe_insert(data_path="location", frame=frame, group="ST-LAT smoke motion")
    if obj.animation_data and obj.animation_data.action:
        for fcurve in obj.animation_data.action.fcurves:
            for key in fcurve.keyframe_points:
                key.interpolation = "LINEAR"

scene.frame_set(1)
bpy.ops.render.render(animation=True)
if not VIDEO.is_file() or VIDEO.stat().st_size < 1024:
    raise RuntimeError(f"Blender did not produce a plausible MP4: {VIDEO}")

report = {
    "schema": "stlat.video-smoke.v1",
    "status": "rendered",
    "video_file": str(VIDEO.relative_to(ROOT)),
    "bytes": VIDEO.stat().st_size,
    "frame_start": scene.frame_start,
    "frame_end": scene.frame_end,
    "expected_frames": scene.frame_end - scene.frame_start + 1,
    "fps": scene.render.fps,
    "resolution": [scene.render.resolution_x, scene.render.resolution_y],
    "animated_character_parts": len(character_parts),
    "motion": {"kind": "deterministic_smoke_fixture", "x_offset_peak_m": 0.65, "returns_to_start": True},
    "ai_video_model_connected": False,
    "ai_motion_plan_applied": False,
    "scope_note": "Validates Blender-to-MP4 rendering only; not AI video generation or visual identity continuity."
}
REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print("STLAT_VIDEO_SMOKE=PASS")
print(json.dumps(report, sort_keys=True))
