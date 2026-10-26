"""Download the MediaPipe model bundles and verify their SHA-256 hashes.

Usage (from the repository root):  python local-app/scripts/download_models.py
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.vision.model_assets import ALL_MODELS, models_dir, sha256_of

TIMEOUT_S = 60


def main() -> int:
    target = models_dir()
    target.mkdir(parents=True, exist_ok=True)
    failures = 0
    for asset in ALL_MODELS:
        path = target / asset.filename
        if path.is_file() and sha256_of(path) == asset.sha256:
            print(f"[ok]       {asset.filename} already present and verified")
            continue
        print(f"[download] {asset.description}\n           {asset.url}")
        try:
            with urllib.request.urlopen(asset.url, timeout=TIMEOUT_S) as response:
                data = response.read()
        except OSError as exc:
            print(f"[error]    download failed: {exc}")
            failures += 1
            continue
        digest = hashlib.sha256(data).hexdigest()
        if digest != asset.sha256:
            print(f"[error]    hash mismatch for {asset.filename}: got {digest}")
            failures += 1
            continue
        tmp = path.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(path)
        print(f"[ok]       saved {path} ({len(data) / 1e6:.1f} MB, SHA-256 verified)")
    if failures:
        print(f"{failures} model(s) could not be installed.")
        return 1
    print("All models installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
