# Character Reference Manifest v1

This manifest is the machine-readable intake contract for source-image-first reconstruction. It is a contract and validator, not yet a model importer, image-understanding model, or editor.

## Core rule

- If the uploaded image includes a character and an environment, preserve both as reconstruction targets: visible objects, background, lighting, color, framing, and composition.
- If the image shows only a character, do not borrow an environment from the imported 3D model or invent one. Mark the scene as character-only and use an explicitly neutral/empty staging area only for inspection.
- The image and explicit user edits outrank the imported model when they disagree.
- A visual style is a render treatment only. It cannot silently redesign source-defined traits or erase the depicted environment.
- Unseen 3D geometry is unknown/inferred until more views or user approval resolve it.
- Intentional deformation and unusual proportions are valid user-authored edits. The system must not automatically “fix” them. Preserve the original asset and record each edit as a revision.

## Manifest and validator

- Schema: `docs/schemas/character-reference-manifest.v1.schema.json`
- Example template: `docs/examples/character-reference-manifest.v1.json`
- Dependency-free contract validator: `scripts/validate_character_reference_manifest.py`

The validator checks the contract invariants and includes negative self-tests. It does not yet parse arbitrary image files, import 3D models, calculate geometry, or compare rendered pixels to the reference.
