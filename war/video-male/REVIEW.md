# Review: male presenter, light theme
This is a copy of `video` (English) with three changes:
- **Voice:** ElevenLabs voice Chris for every line. Each reveal was re-timed by aligning Alice's word timestamps to his.
- **Presenter:** a male avatar drawn from the speaker's photo: short dark hair swept up at the front, black rectangular glasses, full face with light stubble, navy blazer over a white tee, earpiece mic. Lip sync works as in `video`, now with teeth.
- **Theme:** light. Every color was mapped in a single pass by `tools/lighten.py`.
- **Check:** 0 errors, 0 warnings. Render: `../renders/6-EN-male-light.mp4`.

## Rebuild
Git doesn't hold the voice WAVs or the Lucide icons, so a fresh checkout can't render as is. Steps:
1. Voice: generate `assets/voice/s0.wav` to `s8.wav` from `narration/s0.txt` to `s8.txt` with ElevenLabs (voice Chris `iP95p4xoKVk53GoZ742B`, model `eleven_v4`). Then transcribe each take into `narration/words/sN.json`.
2. Icons: put a copy of `lucide-static` (ISC) at `tools/lucide/package/`.
3. Run, in this order:
   - `python3 tools/build_av.py . en scenes`: writes intro/outro (dark theme)
   - `python3 tools/tighten.py .`: scene starts and durations from the voice lengths
   - `AVATAR=male python3 tools/build_av.py . en avatar`: lip-sync data from the WAVs
   - `python3 tools/lighten.py .`: light theme over every scene
   - then `npx hyperframes check` and `render`

The committed compositions are the output of these steps, so you only need them to change a scene.
