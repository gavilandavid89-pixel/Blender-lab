#!/usr/bin/env python3
"""Dependency-free contract checks for ST-LAT neutral scene profiles."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/schemas/scene-profile.v1.schema.json"
PROFILE_PATH = ROOT / "docs/examples/neutral-studio.v1.json"


def fail(message: str) -> None:
    raise SystemExit(f"SCENE_PROFILE_VALIDATION=FAIL: {message}")


def main() -> None:
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read schema/example JSON: {exc}")

    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        fail("schema must declare JSON Schema draft 2020-12")
    if profile.get("schema") != "stlat.scene-profile.v1":
        fail("wrong profile schema identifier")

    required = schema.get("required", [])
    missing = [key for key in required if key not in profile]
    if missing:
        fail(f"profile missing required keys: {missing}")

    props = schema.get("properties", {})
    for key, rule in props.items():
        if key not in profile:
            continue
        if "const" in rule and profile[key] != rule["const"]:
            fail(f"{key} must equal {rule['const']!r}")
        if "enum" in rule and profile[key] not in rule["enum"]:
            fail(f"{key} has unsupported value {profile[key]!r}")

    env = profile["environment"]
    env_rules = props["environment"]["properties"]
    for key in props["environment"]["required"]:
        if key not in env:
            fail(f"environment missing {key}")
    if env["template"] not in env_rules["template"]["enum"]:
        fail("unknown environment template")
    if env["units"] != "meters" or env["deterministic"] is not True:
        fail("neutral studio must use meters and deterministic state")

    defaults = profile["defaults"]
    default_rules = props["defaults"]["properties"]
    for key in props["defaults"]["required"]:
        if key not in defaults:
            fail(f"defaults missing {key}")
    for key, rule in default_rules.items():
        if key not in defaults:
            continue
        if "const" in rule and defaults[key] != rule["const"]:
            fail(f"defaults.{key} violates const")
        if "enum" in rule and defaults[key] not in rule["enum"]:
            fail(f"defaults.{key} has unsupported value")

    camera = profile["camera_policy"]
    camera_rules = props["camera_policy"]["properties"]
    for key in props["camera_policy"]["required"]:
        if key not in camera:
            fail(f"camera_policy missing {key}")
    if camera.get("world_transform_isolation") is not True:
        fail("camera must not mutate world transforms")
    if camera.get("debug_layer_in_final") is not False:
        fail("debug layer must not leak into final render")

    layers = profile["layers"]
    allowed_layers = props["layers"]["items"]["enum"]
    if len(layers) != len(set(layers)):
        fail("layers must be unique")
    unknown_layers = sorted(set(layers) - set(allowed_layers))
    if unknown_layers:
        fail(f"unknown layers: {unknown_layers}")

    forbidden = set(profile["forbidden_implicit_entities"])
    expected_forbidden = {"weapons", "vehicles", "pets", "additional_characters", "furniture", "logos", "text", "weather_effects", "story_props"}
    if not expected_forbidden.issubset(forbidden):
        fail(f"neutral profile omits forbidden implicit entities: {sorted(expected_forbidden - forbidden)}")
    if defaults["props_policy"] != "no_unrequested_narrative_entities":
        fail("neutral profile must forbid unrequested narrative entities")
    if defaults["motion"] != "idle":
        fail("neutral fallback must not invent motion")
    if profile.get("selection", {}).get("source") != "template_default":
        fail("example must mark the profile as a template default, not a confirmed fact")

    print("SCENE_PROFILE_VALIDATION=PASS")
    print(json.dumps({
        "schema": profile["schema"],
        "profile_id": profile["profile_id"],
        "version": profile["version"],
        "template": env["template"],
        "layers_checked": len(layers),
        "implicit_entity_categories_forbidden": len(forbidden),
        "camera_world_isolation": camera["world_transform_isolation"],
        "debug_layer_in_final": camera["debug_layer_in_final"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
