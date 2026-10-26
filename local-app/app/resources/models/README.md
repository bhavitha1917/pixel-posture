# MediaPipe model bundles

This folder holds the two model files the desktop app needs. They are **not** committed
(`*.task` is git-ignored). Install them with:

```powershell
python local-app/scripts/download_models.py
```

| File | Source | License | SHA-256 |
|---|---|---|---|
| `pose_landmarker_lite.task` | `https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task` | Apache-2.0 (Google) | `59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a` |
| `face_landmarker.task` | `https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task` | Apache-2.0 (Google) | `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff` |

The download script and the app both verify these hashes before the models are used
(`app/vision/model_assets.py`). Model cards:
<https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker#models> and
<https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker#models>.
