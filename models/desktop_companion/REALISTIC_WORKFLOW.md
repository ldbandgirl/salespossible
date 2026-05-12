# Realistic Human-Like Desktop Companion (Photo-Matched) Workflow

To get a model that **looks like your exact reference person** (realistic human), a single full-body image is usually not enough for high-fidelity geometry and face likeness.

## Why the first model failed
- It was intentionally low-poly/procedural.
- It had no texture projection from your actual face.
- It had no anatomical sculpting and no rig.

## Minimum inputs for realistic likeness
Capture 20–80 photos:
- Neutral expression, even lighting.
- Front, 45°, side, and back views.
- Head close-ups + full body.
- Same clothing as desired final avatar.

## Recommended production pipeline
1. **Photogrammetry / single-person reconstruction**
   - Polycam, RealityCapture, or Kiri Engine.
2. **Retopology + cleanup in Blender**
   - Target 25k–60k tris for real-time desktop companion.
3. **Bake PBR textures**
   - Albedo, normal, roughness, AO (2K recommended).
4. **Rigging**
   - Mixamo auto-rig or Rigify (humanoid skeleton).
5. **Export GLB**
   - Prefer `.glb` over `.obj` for single-file runtime usage.

## Runtime targets (desktop companion)
- Triangles: 25k–60k
- Texture set: 2K PBR
- Animations: idle, walk, turn, wave
- Format: `companion_realistic.glb`

## What this repo now contains
- A baseline low-poly OBJ (`companion_mobile.obj`) from the earlier pass.
- Guidance to produce a **realistic look-alike v2** with proper scan/retopo/rig/export.

## If you want exact likeness next
Provide:
- 20+ photos (or a short 360 video)
- desired style: photoreal or stylized-real
- runtime engine (Three.js, Unity, Unreal, custom)

Then we can build a true look-alike GLB with rig + animations.
