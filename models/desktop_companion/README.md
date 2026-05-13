# Mobile Desktop Companion 3D Model

This folder contains a lightweight **OBJ + MTL** 3D character model inspired by your reference photo, optimized for use as an AI desktop companion.

## Files
- `companion_mobile.obj` — mesh geometry
- `companion_mobile.mtl` — material definitions/colors

## Design goals
- Smoother mid-poly mesh for more human-like curves while staying runtime-friendly.
- Human-like silhouette with blazer/shirt/pants palette matching the source image.
- Added a subtle hover-ring accent (`accent` material) to emphasize mobility.

## Recommended import settings
When importing into your target app or pipeline:
- Scale: `1.0` (model is authored in meters; approx. 1.78m tall)
- Up axis: `Y`
- Forward axis: `-Z` (or adjust to your engine default)
- Import materials from `.mtl`

## Optional next upgrades
- Add skeletal rig (hips/spine/arms/legs) for idle and walking animations.
- Bake textures for face details and clothing seams.
- Export to `.glb` once rigged/animated for single-file deployment.


## Realistic look-alike note
A single-image procedural OBJ cannot reliably produce exact human likeness. See `REALISTIC_WORKFLOW.md` and `generation_prompts.txt` for the realistic pipeline and prompts to generate a true photo-matched GLB avatar.


## Mesh update
- Replaced the original blocky procedural mesh with a smoother mid-poly body built from lathed surfaces and a torus hover ring.
- Current mesh density is suitable as a better visual base before full photoreal scan/retopo work.
