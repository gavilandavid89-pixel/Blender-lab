#!/usr/bin/env python3
"""Dependency-free checks for the character-reference manifest contract."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/schemas/character-reference-manifest.v1.schema.json"
EXAMPLE_PATH = ROOT / "docs/examples/character-reference-manifest.v1.json"


def validate(schema: dict, manifest: dict) -> list[str]:
    errors: list[str] = []
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append("schema must declare JSON Schema draft 2020-12")
    if manifest.get("schema") != "stlat.character-reference-manifest.v1":
        errors.append("wrong manifest schema identifier")
    for key in schema.get("required", []):
        if key not in manifest:
            errors.append(f"missing required top-level field: {key}")
    if errors:
        return errors
    if schema.get("additionalProperties") is False:
        extra = sorted(set(manifest) - set(schema.get("properties", {})))
        if extra:
            errors.append(f"unexpected top-level fields: {extra}")
    source = manifest["source"]
    if source.get("immutable") is not True:
        errors.append("source must remain immutable")
    if source.get("sha256") is not None and not re.fullmatch(r"[a-fA-F0-9]{64}", source["sha256"]):
        errors.append("source.sha256 must be null or 64 hexadecimal characters")
    scope = manifest["reference_scope"]
    if not scope.get("images"):
        errors.append("at least one source reference image is required")
    mode = scope.get("mode")
    env_policy = scope.get("environment_policy")
    if mode == "character_and_environment" and env_policy != "reconstruct_visible_environment":
        errors.append("image with environment must reconstruct the visible environment")
    if mode == "character_only" and env_policy != "no_environment_in_source":
        errors.append("character-only image must not invent an environment from a model")
    identity = manifest["identity_policy"]
    if identity.get("authority") != "source_reference_and_explicit_user_edits":
        errors.append("source reference and explicit user edits must remain authoritative")
    if identity.get("unknown_geometry_policy") != "label_as_inferred_or_unknown":
        errors.append("unknown geometry must be labeled inferred or unknown")
    must_not_change = set(identity.get("style_must_not_change", []))
    required_protected = {"face", "eyes", "hair", "silhouette", "body_proportions", "clothing", "accessories", "markings", "source_environment", "composition"}
    if not required_protected.issubset(must_not_change):
        errors.append(f"style contract omits protected source traits: {sorted(required_protected - must_not_change)}")
    model = manifest["model_asset"]
    if model.get("source_preserved") is not True:
        errors.append("model source must remain recoverable")
    if model.get("sha256") is not None and not re.fullmatch(r"[a-fA-F0-9]{64}", model["sha256"]):
        errors.append("model_asset.sha256 must be null or 64 hexadecimal characters")
    if manifest["editing"].get("allow_deliberate_deformation") is not True:
        errors.append("deliberate user deformation must be allowed")
    if manifest["editing"].get("automatic_identity_repair") is not False:
        errors.append("automatic identity repair must be disabled")
    for image in scope["images"]:
        if image.get("sha256") is not None and not re.fullmatch(r"[a-fA-F0-9]{64}", image["sha256"]):
            errors.append(f"invalid image hash for {image.get('image_id', '<unknown>')}")
    return errors


def main() -> None:
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        manifest = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"CHARACTER_REFERENCE_MANIFEST=FAIL: cannot read schema/example: {exc}")
    errors = validate(schema, manifest)
    if errors:
        raise SystemExit("CHARACTER_REFERENCE_MANIFEST=FAIL: " + "; ".join(errors))
    cases = []
    bad = copy.deepcopy(manifest); bad["source"]["immutable"] = False
    cases.append(("immutable source", bad, "source must remain immutable"))
    bad = copy.deepcopy(manifest); bad["reference_scope"]["mode"] = "character_only"
    cases.append(("character-only must not invent environment", bad, "character-only image must not invent an environment"))
    bad = copy.deepcopy(manifest); bad["editing"]["automatic_identity_repair"] = True
    cases.append(("no silent repair", bad, "automatic identity repair must be disabled"))
    bad = copy.deepcopy(manifest); bad["editing"]["allow_deliberate_deformation"] = False
    cases.append(("deliberate deformation", bad, "deliberate user deformation must be allowed"))
    bad = copy.deepcopy(manifest); bad["model_asset"]["source_preserved"] = False
    cases.append(("preserve model source", bad, "model source must remain recoverable"))
    for label, candidate, expected in cases:
        found = validate(schema, candidate)
        if not any(expected in message for message in found):
            raise SystemExit(f"CHARACTER_REFERENCE_MANIFEST=FAIL: negative test did not reject {label}: {found}")
    print("CHARACTER_REFERENCE_MANIFEST=PASS")
    print(json.dumps({"schema": manifest["schema"], "reference_mode": manifest["reference_scope"]["mode"], "environment_policy": manifest["reference_scope"]["environment_policy"], "negative_cases_passed": len(cases), "deliberate_deformation_allowed": manifest["editing"]["allow_deliberate_deformation"], "automatic_identity_repair": manifest["editing"]["automatic_identity_repair"]}, indent=2))


if __name__ == "__main__":
    main()
