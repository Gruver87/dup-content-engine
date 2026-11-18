# Character / 3D scan — peers vs DUP

Fail-closed: this doc describes **how top products work**, not a claim that DUP ships HeyGen-class photoreal.

## Two industries under one word “avatar”

| Class | Examples | Mechanism | Realistic / cartoon | Cost for laptop-first |
| --- | --- | --- | --- | --- |
| Photoreal video DiT | HeyGen Avatar V, Synthesia Express-2, D-ID V4 | Reference tokens + audio → latent video → identity SR | “Realism” = neural video, not a classic mesh | Cloud/GPU + keys |
| 3DMM / lip-sync OSS | SadTalker, MuseTalk, LatentSync, Wav2Lip | Photo/video + audio → face motion | Face realism; not full-body 3D scene | VRAM; check licenses |
| True 3D browser | TalkingHead + VRoid / Ready Player Me | Three.js + GLB (Mixamo + ARKit/Oculus visemes) | Anime (VRoid) / semi-real (RPM) | Needs authored `.glb` |
| Style identity | CapCut Dreamina / Seedream | Character ref + style ref → consistent plates | Cartoon / comic / photo look | Gen-cloud |

## DUP hybrid (shipped path)

1. **Local Character Kit** — styles: `cartoon`, `anime`, `mascot`, `clay`, `realistic_stylized` (stylized, not Avatar V).
2. **Pillow plates → ffmpeg clips** — speaker + emotion + style → bust plate under captions.
3. **Ops Console 3D preview** — procedural Three.js bust; if `assets/avatars/*.glb` exists → GLTF mesh preview (lip-sync TalkingHead not wired yet).
4. **CLI** — `dup-content character-preview --style cartoon --speaker Fox`.
5. **Optional cloud** — existing `avatar.py` HeyGen adapter (keys); never required for demo green.

## Have / miss

| Have | Miss (honest) |
| --- | --- |
| Style bank + local plates | Seedance / Dreamina Gen |
| Console 3D procedural preview | Photoreal teeth/pores like Avatar V |
| Optional HeyGen CLI | SadTalker GPU out-of-box |
| GLB mesh preview when file in `assets/avatars/` | Full TalkingHead runtime / Azure visemes |
| Rule-based morph drive (Oculus/ARKit names) | Guaranteed morphs on every GLB |

## Refuse

- Claiming ALLOW demo = HeyGen quality
- Shipping GPU models as “offline green” without evidence
- Cookie bots / scraped donor faces as “realistic characters”
