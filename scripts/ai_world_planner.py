#!/usr/bin/env python3
"""Propose safe ST-LAT world edits with Groq; never mutates the world automatically.

Requires GROQ_API_KEY. Uses only Python's standard library so the lab stays light.
The model may propose transforms for existing entities only. Creation/deletion,
identity changes, and Blender execution are intentionally outside this first adapter.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-20b"


class PlannerError(ValueError):
    pass


def _finite_vector3(value: Any) -> bool:
    return (
        isinstance(value, list) and len(value) == 3
        and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in value)
    )


def validate_plan(plan: Any, snapshot: Any) -> list[str]:
    """Validate the model's proposal against current IDs and world bounds."""
    errors: list[str] = []
    if not isinstance(plan, dict):
        return ["plan must be a JSON object"]
    if not isinstance(snapshot, dict):
        return ["snapshot must be a JSON object"]
    if not isinstance(plan.get("summary"), str) or not plan["summary"].strip():
        errors.append("summary must be a non-empty string")
    operations = plan.get("operations")
    if not isinstance(operations, list):
        return errors + ["operations must be an array"]
    entities = snapshot.get("entities")
    if not isinstance(entities, list):
        return errors + ["snapshot.entities must be an array"]
    by_id = {e.get("id"): e for e in entities if isinstance(e, dict) and isinstance(e.get("id"), str)}
    bounds = snapshot.get("bounds")
    if not isinstance(bounds, dict) or not _finite_vector3(bounds.get("min")) or not _finite_vector3(bounds.get("max")):
        return errors + ["snapshot.bounds must contain finite min/max vector3 values"]

    seen: set[str] = set()
    for i, op in enumerate(operations):
        prefix = f"operations[{i}]"
        if not isinstance(op, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if op.get("type") != "transform_updated":
            errors.append(f"{prefix}.type must be transform_updated; this adapter cannot create/delete entities")
        target = op.get("target_id")
        if not isinstance(target, str) or target not in by_id:
            errors.append(f"{prefix}.target_id must identify an existing entity")
            continue
        if target in seen:
            errors.append(f"{prefix} duplicates target_id {target}")
        seen.add(target)
        transform = op.get("transform")
        if not isinstance(transform, dict):
            errors.append(f"{prefix}.transform must be an object")
            continue
        for key in ("position", "rotation_euler_rad", "scale"):
            if not _finite_vector3(transform.get(key)):
                errors.append(f"{prefix}.transform.{key} must be a finite vector3")
        scale = transform.get("scale")
        if _finite_vector3(scale) and any(v <= 0 for v in scale):
            errors.append(f"{prefix}.transform.scale values must be positive")
        position = transform.get("position")
        if _finite_vector3(position):
            if any(position[j] < bounds["min"][j] or position[j] > bounds["max"][j] for j in range(3)):
                errors.append(f"{prefix}.transform.position exceeds hard world bounds")
            role = str(by_id[target].get("role", "")).lower()
            if not role.startswith("camera") and position[2] < bounds["min"][2]:
                errors.append(f"{prefix}.transform.position is below the world floor")
        if "identity_ref" in op or "identity_signature" in op or "asset_id" in op or "appearance_id" in op:
            errors.append(f"{prefix} cannot modify protected identity fields")
    return errors


def request_plan(prompt: str, snapshot: dict[str, Any], api_key: str, model: str = DEFAULT_MODEL,
                 endpoint: str = DEFAULT_ENDPOINT, timeout: int = 45) -> dict[str, Any]:
    entities = snapshot.get("entities")
    if not isinstance(entities, list):
        raise PlannerError("snapshot.entities must be an array")
    compact_entities = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        compact_entities.append({
            "id": entity.get("id"), "role": entity.get("role"),
            "transform": entity.get("transform"),
            "identity_ref": entity.get("identity_ref"),
            "attributes": entity.get("attributes", {}),
        })
    world_context = {
        "world_id": snapshot.get("world_id"),
        "version": snapshot.get("version"),
        "units": snapshot.get("units"),
        "axes": snapshot.get("axes"),
        "bounds": snapshot.get("bounds"),
        "entities": compact_entities,
    }
    system_prompt = (
        "You are the planning component for ST-LAT, a persistent 3D world engine. "
        "Return only a JSON object with keys summary and operations. Each operation must be "
        "{type:'transform_updated', target_id:string, reason:string, transform:{position:[x,y,z], "
        "rotation_euler_rad:[x,y,z], scale:[x,y,z]}}. Use meters, radians, and the supplied axes. "
        "Only target IDs that exist in the supplied snapshot. Preserve every entity's identity, "
        "role, parent, asset and appearance. Do not invent IDs. Do not emit create/delete operations. "
        "Keep all positions within hard world bounds and all scales positive. Include only entities "
        "that need to move; preserve untouched transforms exactly. If the request is ambiguous, return "
        "operations:[] and explain the ambiguity in summary."
    )
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "WORLD SNAPSHOT (read-only):\n"
             + json.dumps(world_context, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
             + "\nUSER REQUEST:\n" + prompt},
        ],
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Explicit UA avoids the default Python-urllib signature that can trigger Cloudflare 1010.
            "User-Agent": "ST-LAT-World3D-Lab/1.0 (+https://github.com/gavilandavid89-pixel/Blender-lab)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Do not print request headers or the API key.
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise PlannerError(f"AI provider returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PlannerError(f"AI request failed: {exc}") from exc
    try:
        content = body["choices"][0]["message"]["content"]
        plan = json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise PlannerError("AI response did not contain valid JSON plan content") from exc
    errors = validate_plan(plan, snapshot)
    if errors:
        raise PlannerError("unsafe or invalid AI plan: " + "; ".join(errors))
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True, help="canonical world-state snapshot JSON")
    parser.add_argument("--prompt", required=True, help="natural-language request for the world planner")
    parser.add_argument("--model", default=os.environ.get("STLAT_AI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--endpoint", default=os.environ.get("STLAT_AI_ENDPOINT", DEFAULT_ENDPOINT))
    parser.add_argument("--output", type=Path, help="optional path for the proposal JSON")
    args = parser.parse_args()
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("STLAT_AI_PLANNER=SKIP: set GROQ_API_KEY in the environment; never commit the key.", file=sys.stderr)
        return 2
    try:
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        plan = request_plan(args.prompt, snapshot, api_key, args.model, args.endpoint)
    except (OSError, json.JSONDecodeError, PlannerError) as exc:
        print(f"STLAT_AI_PLANNER=FAIL: {exc}", file=sys.stderr)
        return 1
    rendered = json.dumps({"schema": "stlat.ai-world-plan.v1", "status": "proposed",
                           "model": args.model, "plan": plan}, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    print("STLAT_AI_PLANNER=PROPOSAL_VALIDATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
