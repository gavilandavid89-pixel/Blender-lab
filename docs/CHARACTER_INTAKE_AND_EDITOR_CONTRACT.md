# ST-LAT Character Intake & Visual Editor Contract v1

## Purpose and status

This document defines the next implementation contract for importing a character reference/model, validating its geometry, preserving its identity, and letting a user adjust it in a 3D editor. It is a specification, not a claim that the full editor or import pipeline already exists.

## Non-negotiable precedence: source character reference wins

The user-provided character image(s) are the authority for the character's recognizable appearance. A selected art-style profile is a rendering treatment, not permission to redesign the character.

Priority order:
1. Explicit user edits to the character/reference profile.
2. User-supplied reference images and approved model asset for identity-defining traits.
3. Selected style profile for presentation choices that do not contradict identity.
4. Generic engine defaults only where the user has supplied no evidence or preference.

The style profile may affect shading, outlines, lighting, color-management, background, and render treatment. It must not silently change the face shape, eye design, hair silhouette/color, body proportions, clothing, accessories, markings, or other traits visible in the source reference. If the chosen style and source image conflict, preserve the source traits and show a conflict/warning rather than guessing.

A 2D image is not a complete geometric specification. It cannot by itself establish hidden/back-side geometry, exact depth, topology, rig, or physically accurate dimensions. For unseen features the editor must label values as inferred/defaulted and permit user correction. Multiple views improve confidence but do not constitute a mathematical guarantee.

## Character intake pipeline

### Stage 1 — Import without modifying the source

- Keep the original file/reference immutable; record source URI or managed asset reference, file hash when available, import timestamp, importer version, and user-provided notes.
- Import into an isolated staging collection/scene. Do not add an unvalidated asset to the canonical world.
- Record file format, object count, mesh count, materials, textures, armatures, animation clips, units, coordinate orientation, and import warnings.
- Treat filenames and embedded metadata as untrusted hints, not authoritative identity.

### Stage 2 — Geometry and unit inspection

Measure evaluated geometry, not just metadata:
- world-space and local-space bounds, height/width/depth, origin, object transforms, and scale;
- mesh vertex/face counts, empty meshes, non-finite coordinates, degenerate geometry where detectable, normals, disconnected components where relevant;
- transforms and modifiers that alter evaluated geometry;
- unit and axis conversion, with a reversible import record.

No automatic non-uniform scaling is allowed as a silent repair. A uniform unit conversion is allowed only when its interpretation is clear and recorded. Ambiguous scale/orientation must require user confirmation. Preserve the source asset so any normalization can be undone.

### Stage 3 — Proportion profile

The user may inspect and, when needed, edit:
- overall height and unit interpretation;
- width/depth envelope;
- head-to-body, torso-to-leg, arm-to-body, and other chosen landmark ratios when those landmarks can be reliably measured;
- ground contact/foot baseline and origin/pivot;
- forward axis and up axis;
- uniform scale and placement in the world.

The UI must distinguish measured, inferred, and user-adjusted values. Do not invent precise anatomy measurements from an arbitrary single view. If a proportion cannot be reliably derived from geometry or reference views, show "unknown / needs review," not a fabricated value.

Proportion editing defaults to preserving geometry and changing only the documented import transform. Actual vertex deformation is a separate, explicitly named operation that previews its effects and can be undone. It must never be applied automatically merely to fit a room or match a generic human template.

### Stage 4 — Rig and animation readiness

- Detect whether an armature exists and whether mesh objects are weighted to it.
- Inspect bone hierarchy, missing/invalid weights, rest pose, scale consistency, and available animation actions to the extent supported.
- Assign readiness states: static_mesh, rig_present_unverified, rig_validated_for_profile, or rig_rejected.
- A rig-presence check is not proof of good animation. Use a standard pose/motion smoke test before enabling the character for animation-driven scenes.
- Do not fabricate a rig silently. Any auto-rigging workflow must be a separate opt-in step with a preview and rollback.

### Stage 5 — Identity manifest and lock

Create a versioned manifest containing:
- stable character ID and asset version;
- source asset hash/reference and import settings;
- geometry fingerprint where deterministic hashing is supported;
- measured dimensions and units;
- reference-image references and user-approved identity traits;
- material/texture inventory and their references;
- rig status and rig fingerprint when present;
- user adjustments and provenance;
- visual-style profile ID/version;
- confidence/warning list and validation report.

Protect identity-defining fields from ordinary scene-planning AI operations. Updating the underlying model, materials, proportions, or rig creates a new asset version and requires explicit user action plus a comparison report. A geometry hash detects byte/geometry changes but cannot, alone, prove visual identity.

## Visual style profile behavior

A profile is a versioned rendering preset, not an identity generator. It may define renderer, shading model, outline method, shadow bands, lighting defaults, color management, render resolution, and output settings.

The pipeline should separate:
- identity layer: source image/model, approved proportions, face/hair/clothing/accessories, identity manifest;
- presentation layer: toon/cel shading, outlines, lighting, camera treatment, post-processing;
- scene layer: world position, interactions, collisions, environment and animation.

Changing a style profile must not mutate the identity layer or canonical world transforms. If a shader or render technique makes an identity feature unreadable, flag it for review instead of altering the feature.

## 3D editor UI contract

The editor must expose the following areas, designed for desktop and touch use:

### A. Viewport
- Orbit, pan, zoom, front/side/back/top and perspective/orthographic views.
- Toggle wireframe, solid, material preview, rendered preview, skeleton overlay, bounds and measurement guides.
- Reference-image panels with opacity, alignment, and front/side/back slots when supplied.
- Clear selection highlight and a "show original vs adjusted" comparison.

### B. Character properties panel
- Asset identity and validation status.
- Units, height/width/depth, scale, origin/pivot, ground contact and forward/up axes.
- Proportion measurements with measured/inferred/user-adjusted badges.
- Mesh/material/texture inventory.
- Rig readiness and test status.
- Identity lock, source hash/version, and change history.

### C. Safe editing controls
- Uniform scale is the default; axis-specific scale is an advanced control with a visible warning because it can distort proportions.
- Pivot/origin changes and ground alignment have explicit buttons and undo.
- Proportion or vertex edits are opt-in, previewed, undoable, and recorded as a new revision.
- "Fit to room" may reposition or uniformly scale only after user confirmation; it must not deform the body.
- Reset-to-imported and compare-to-source actions are always available.

### D. Style panel
- Choose a named style profile and version.
- Preview shading/outline/lighting independently of geometry.
- Display a warning if the style obscures or contradicts source identity traits.
- Switching style must not alter the asset manifest's identity fields.

### E. Validation and commit flow
1. Import into staging.
2. Run geometry/scale/rig checks.
3. Review warnings and source-reference comparisons.
4. Make explicit user adjustments.
5. Run validation again.
6. Show a diff against the original import and identity manifest.
7. Commit as a new approved asset version only after explicit confirmation.
8. Keep the original source and previous versions recoverable.

### F. Touch/mobile usability
- Large labeled controls, no hover-only actions, and a collapsible properties drawer.
- Viewport remains usable when the keyboard opens; text fields support paste.
- Editing values must not cause the viewport to unexpectedly resize or lose the current selection.
- Provide a simplified mobile layout and a full editor layout without hiding essential validation status.

## Required failure behavior

Reject or quarantine the staged asset if geometry contains invalid/non-finite data, dimensions cannot be measured, required conversions are ambiguous, IDs conflict, or a required validation fails. Report the reason and preserve the original input. Never silently replace a failed asset with a proxy while reporting success.

If a property cannot be measured, label it unknown. If a visual comparison is uncertain, request review. A successful import means the asset passed the stated checks; it does not guarantee perfect anatomy, animation, or video continuity.

## Acceptance tests

1. Importing the same asset with the same importer settings produces the same stable manifest fields and geometry fingerprint where supported.
2. Unit conversion is reversible and produces expected measured dimensions.
3. An ambiguous scale triggers a confirmation requirement rather than automatic distortion.
4. The source file/hash and original transform remain recoverable after normalization.
5. Applying a style profile changes render treatment but leaves geometry, identity fields, and world transforms unchanged.
6. A conflicting style/identity setting raises a visible warning and preserves the reference-defined trait.
7. The UI clearly distinguishes measured, inferred, and user-edited values.
8. Invalid geometry and missing rig requirements block only the capabilities that depend on them and produce actionable reports.
9. User edits are undoable and create a versioned diff; AI scene proposals cannot edit protected identity fields.
10. Staging failure leaves the canonical world and prior asset version unchanged.
11. Front/side/back reference views, when supplied, remain associated with the same character version.
12. Mobile UI allows selecting, measuring, editing, pasting values, previewing and confirming without losing state.

## Explicit limitations

No single image can guarantee complete 3D reconstruction. A valid AABB does not prove anatomical correctness. A present armature does not prove a valid rig. A deterministic manifest does not prove visual similarity. Render and video evaluators will need separate visual regression tests, with human review for ambiguous cases.
