#!/usr/bin/env python3
"""Safely apply a validated ST-LAT snapshot to existing Blender mesh objects."""
from __future__ import annotations
import copy, json, math, sys, tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from world_state_contract import AXES, validate_state  # noqa: E402
from world_state_replay import canonical_state_json, replay_events  # noqa: E402
from world_state_store import WorldStateStore  # noqa: E402
DEFAULT_REPORT = ROOT / "artifacts/stlat-world-state-blender-sync.json"
TOL = 1e-4


class BlenderSyncError(ValueError):
    pass


def _vec3(value: Any) -> bool:
    return isinstance(value, (list, tuple)) and len(value) == 3 and all(
        isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in value
    )


def _near(a: Any, b: Any) -> bool:
    # Blender's mathutils.Vector is sequence-like but is not a list/tuple.
    try:
        if len(a) != 3 or len(b) != 3:
            return False
        av, bv = [a[i] for i in range(3)], [b[i] for i in range(3)]
    except (TypeError, KeyError, IndexError):
        return False
    return all(
        isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
        and isinstance(y, (int, float)) and not isinstance(y, bool) and math.isfinite(y)
        and abs(float(x) - float(y)) <= TOL
        for x, y in zip(av, bv)
    )


def _id(obj: Any) -> str | None:
    value = obj.get("stlat_id")
    return value if isinstance(value, str) and value.strip() else None


def _aabb(obj: Any, bpy: Any) -> dict[str, list[float]]:
    from mathutils import Vector
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    corners = [evaluated.matrix_world @ Vector(c) for c in evaluated.bound_box]
    if not corners:
        raise BlenderSyncError(f"{obj.name}: empty evaluated bounds")
    return {key: [fn(float(p[i]) for p in corners) for i in range(3)]
            for key, fn in (("min", min), ("max", max))}


def _bounds_match(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    return _near(actual.get("min"), expected.get("min")) and _near(actual.get("max"), expected.get("max"))


def _aabb_overlaps(a: dict[str, Any], b: dict[str, Any]) -> bool:
    # Touching faces are allowed; positive-volume overlap beyond tolerance is a collision.
    return all(
        float(a["max"][i]) > float(b["min"][i]) + TOL
        and float(a["min"][i]) < float(b["max"][i]) - TOL
        for i in range(3)
    )


def _shift_bounds(bounds: dict[str, Any], delta: list[float]) -> dict[str, Any]:
    return {
        key: [float(value) + float(delta[i]) for i, value in enumerate(bounds[key])]
        for key in ("min", "max")
    }


def _transform_match(obj: Any, t: dict[str, Any]) -> bool:
    return _near(obj.location, t["position"]) and _near(obj.rotation_euler, t["rotation_euler_rad"]) and _near(obj.scale, t["scale"])


def _preflight(snapshot: Any, scene: Any) -> list[tuple[dict[str, Any], Any]]:
    errors = validate_state(snapshot)
    if errors:
        raise BlenderSyncError("invalid world snapshot: " + "; ".join(errors))
    by_id: dict[str, Any] = {}
    duplicates: set[str] = set()
    for obj in scene.objects:
        oid = _id(obj)
        if oid:
            if oid in by_id:
                duplicates.add(oid)
            by_id[oid] = obj
    if duplicates:
        raise BlenderSyncError("duplicate scene stlat_id values: " + ", ".join(sorted(duplicates)))
    targets = []
    for entity in snapshot["entities"]:
        obj = by_id.get(entity["id"])
        if obj is None:
            raise BlenderSyncError(f"no Blender object matches entity id {entity['id']!r}")
        if obj.type != "MESH":
            raise BlenderSyncError(f"{entity['id']!r} maps to {obj.type}; only MESH is supported")
        if obj.parent is not None:
            raise BlenderSyncError(f"{entity['id']!r} is parented; world/local transform semantics are not implemented")
        if obj.get("stlat_role") != entity["role"]:
            raise BlenderSyncError(f"role mismatch for {entity['id']!r}")
        targets.append((entity, obj))
    return targets


def apply_snapshot(snapshot: Any, scene: Any, bpy: Any) -> dict[str, Any]:
    """Preflight every target, apply transforms, verify evaluated AABBs, rollback on error."""
    targets = _preflight(snapshot, scene)
    original = {e["id"]: (list(o.location), list(o.rotation_euler), list(o.scale)) for e, o in targets}
    try:
        for entity, obj in targets:
            t = entity["transform"]
            obj.location, obj.rotation_euler, obj.scale = t["position"], t["rotation_euler_rad"], t["scale"]
        bpy.context.view_layer.update()
        failures = []
        for entity, obj in targets:
            if not _transform_match(obj, entity["transform"]):
                failures.append(f"{entity['id']}: transform read-back mismatch")
                continue
            actual_bounds = _aabb(obj, bpy)
            if not _bounds_match(actual_bounds, entity["bounds"]):
                failures.append(f"{entity['id']}: evaluated AABB differs from snapshot")
                continue
            if entity.get("collision") == "solid":
                role = entity["role"]
                for obstacle in scene.objects:
                    if obstacle is obj or obstacle.type != "MESH":
                        continue
                    obstacle_role = obstacle.get("stlat_role", "unclassified")
                    if obstacle_role.startswith("debug."):
                        continue
                    if role.startswith("character.") and obstacle_role.startswith("character."):
                        continue
                    if obstacle.get("stlat_collision") in {"none", "trigger"}:
                        continue
                    obstacle_bounds = _aabb(obstacle, bpy)
                    if _aabb_overlaps(actual_bounds, obstacle_bounds):
                        obstacle_label = _id(obstacle) or obstacle.name
                        failures.append(
                            f"{entity['id']}: solid AABB overlaps obstacle {obstacle_label!r} "
                            f"(role={obstacle_role!r})"
                        )
        if failures:
            raise BlenderSyncError("; ".join(failures))
    except Exception:
        for entity, obj in targets:
            loc, rot, scale = original[entity["id"]]
            obj.location, obj.rotation_euler, obj.scale = loc, rot, scale
        bpy.context.view_layer.update()
        raise
    return {
        "status": "success", "world_id": snapshot["world_id"], "version": snapshot["version"],
        "applied_entity_ids": [e["id"] for e, _ in targets], "applied_count": len(targets),
        "saved_blend": False,
        "checks": {"snapshot_contract_valid": True, "all_targets_preflighted": True,
                   "transforms_read_back": True, "evaluated_world_bounds_match": True, "scene_saved": False},
    }


def _entity(obj: Any, bpy: Any, position: list[float] | None = None,
            role: str | None = None, shift_x: float = 0.0) -> dict[str, Any]:
    bounds = _aabb(obj, bpy)
    for key in ("min", "max"):
        bounds[key] = [v + (shift_x if i == 0 else 0.0) for i, v in enumerate(bounds[key])]
    return {
        "id": _id(obj), "role": role if role is not None else obj.get("stlat_role"),
        "transform": {"position": list(position if position is not None else obj.location),
                      "rotation_euler_rad": list(obj.rotation_euler), "scale": list(obj.scale)},
        "bounds": {**bounds, "kind": "aabb"}, "persistence": "dynamic",
        "collision": "solid", "attributes": {},
    }


def _snapshot(entity: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "stlat.world-state.v1", "world_id": "blender-sync-self-test",
            "version": 1, "parent_version": None, "units": "meters", "axes": dict(AXES),
            "bounds": {"min": [-4.0, -4.0, 0.0], "max": [4.0, 4.0, 3.2]},
            "timestamp": 1.0, "entities": [entity], "events": []}


def _other_object_transforms(scene: Any, target: Any) -> dict[str, tuple[tuple[float, ...], ...]]:
    return {
        obj.name: (
            tuple(float(v) for v in obj.location),
            tuple(float(v) for v in obj.rotation_euler),
            tuple(float(v) for v in obj.scale),
        )
        for obj in scene.objects if obj is not target
    }


def run_self_test(scene: Any, bpy: Any) -> dict[str, Any]:
    candidates = [o for o in scene.objects if o.type == "MESH" and o.get("stlat_role") == "character.torso"]
    if len(candidates) != 1:
        raise BlenderSyncError(f"expected exactly one character.torso mesh; found {len(candidates)}")
    obj = candidates[0]
    original = (list(obj.location), list(obj.rotation_euler), list(obj.scale))
    original_entity = _entity(obj, bpy)
    initial_state = _snapshot(original_entity)
    original_bounds = _aabb(obj, bpy)
    moved_pos = [float(obj.location[0]) + 0.25, float(obj.location[1]), float(obj.location[2])]
    moved = _entity(obj, bpy, position=moved_pos, shift_x=0.25)
    other_before = _other_object_transforms(scene, obj)
    checks: dict[str, bool] = {}
    try:
        # Exercise the real path: approved event -> replay -> immutable disk snapshots
        # -> reload latest -> apply the restored state to Blender.
        event = {
            "id": "evt-blender-sync-move",
            "type": "transform_updated",
            "timestamp": 2.0,
            "actor_id": "blender-sync-self-test",
            "target_id": moved["id"],
            "approved": True,
            "payload": {
                "transform": copy.deepcopy(moved["transform"]),
                "bounds": copy.deepcopy(moved["bounds"]),
            },
        }
        replayed = replay_events(initial_state, [event])
        with tempfile.TemporaryDirectory(prefix="stlat-blender-sync-") as temp:
            store = WorldStateStore(Path(temp) / "store")
            store.save_snapshot(initial_state)
            store.save_snapshot(replayed)
            disk_initial = store.load_snapshot(initial_state["world_id"], 1)
            disk_latest = store.load_latest(initial_state["world_id"])
            replayed_from_disk = replay_events(disk_initial, [event])
            checks["persisted_replay_matches_latest"] = (
                canonical_state_json(replayed_from_disk) == canonical_state_json(disk_latest)
            )
            applied = apply_snapshot(disk_latest, scene, bpy)
            checks["persisted_replay_applied_to_blender"] = (
                applied["status"] == "success"
                and _near(obj.location, moved_pos)
                and _bounds_match(_aabb(obj, bpy), moved["bounds"])
            )
        checks["non_target_objects_unchanged"] = _other_object_transforms(scene, obj) == other_before
        checks["valid_transform_applied_and_bounds_verified"] = (
            _near(obj.location, moved_pos) and _bounds_match(_aabb(obj, bpy), moved["bounds"])
        )
        at_moved = list(obj.location)
        wrong_role = copy.deepcopy(moved)
        wrong_role["role"] = "character.invalid"
        try:
            apply_snapshot(_snapshot(wrong_role), scene, bpy)
            checks["role_mismatch_rejected_without_mutation"] = False
        except BlenderSyncError:
            checks["role_mismatch_rejected_without_mutation"] = _near(obj.location, at_moved)
        wrong_bounds = copy.deepcopy(moved)
        wrong_bounds["bounds"]["max"][0] += 0.5
        try:
            apply_snapshot(_snapshot(wrong_bounds), scene, bpy)
            checks["bounds_mismatch_rejected_and_rolled_back"] = False
        except BlenderSyncError:
            checks["bounds_mismatch_rejected_and_rolled_back"] = _near(obj.location, at_moved)

        collision_entity = copy.deepcopy(moved)
        collision_pos = [2.45, 1.20, 0.90]
        delta = [collision_pos[i] - moved_pos[i] for i in range(3)]
        collision_entity["transform"]["position"] = collision_pos
        collision_entity["bounds"] = {
            **_shift_bounds(collision_entity["bounds"], delta), "kind": "aabb"
        }
        try:
            apply_snapshot(_snapshot(collision_entity), scene, bpy)
            checks["solid_collision_rejected_and_rolled_back"] = False
        except BlenderSyncError as exc:
            checks["solid_collision_rejected_and_rolled_back"] = (
                "bed.mattress" in str(exc).lower() and _near(obj.location, at_moved)
            )
        apply_snapshot(initial_state, scene, bpy)
        checks["original_scene_transform_restored"] = (
            _near(obj.location, original[0]) and _near(obj.rotation_euler, original[1])
            and _near(obj.scale, original[2]) and _bounds_match(_aabb(obj, bpy), original_bounds)
        )
    finally:
        obj.location, obj.rotation_euler, obj.scale = original
        bpy.context.view_layer.update()
    return {"schema": "stlat.world-state-blender-sync-report.v1",
            "status": "passed" if all(checks.values()) else "failed",
            "method": "saved-scene end-to-end test: approved event replay, persist/reload/apply, non-target isolation, role/AABB rejection, solid-overlap rejection and rollback",
            "scene_file": "artifacts/stlat-world3d.blend", "target_id": _id(obj),
            "checks": checks, "check_count": len(checks),
            "limitations": ["Existing unparented MESH objects only; stable ID and semantic role must match.",
                "AABB must match evaluated Blender geometry after transform; solid collision checks use final-pose AABBs only.", "No creation, deletion, reparenting, camera/light or animation sync.",
                "The bridge never saves the .blend automatically."]}


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main() -> None:
    import bpy
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    report_path = Path(args[args.index("--report") + 1]) if "--report" in args else DEFAULT_REPORT
    if "--self-test" in args:
        report = run_self_test(bpy.context.scene, bpy)
        _write_report(report_path, report)
        print("STLAT_WORLD_STATE_BLENDER_SYNC=" + json.dumps(report, sort_keys=True))
        if report["status"] != "passed":
            raise RuntimeError("ST-LAT Blender sync self-test failed")
        return
    if "--snapshot" not in args:
        raise SystemExit("Usage: blender --background scene.blend --python scripts/world3d_sync_state.py -- --snapshot state.json [--report report.json]")
    path = Path(args[args.index("--snapshot") + 1])
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        report = apply_snapshot(snapshot, bpy.context.scene, bpy)
    except (OSError, json.JSONDecodeError, BlenderSyncError) as exc:
        report = {"schema": "stlat.world-state-blender-sync-report.v1", "status": "failed",
                  "error": str(exc), "saved_blend": False}
        _write_report(report_path, report)
        raise SystemExit(f"STLAT_WORLD_STATE_BLENDER_SYNC=FAIL: {exc}")
    _write_report(report_path, report)
    print("STLAT_WORLD_STATE_BLENDER_SYNC=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
