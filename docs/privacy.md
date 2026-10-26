# Privacy and security

Pixel Posture handles one of the most sensitive data streams on a computer: a live camera
feed. This document records what the app does with it, what it stores, and the threats it is
designed against, at a level appropriate for a student project.

## Data inventory

| Data | Where it lives | Leaves the PC? | Persisted? |
|---|---|---|---|
| Camera frames | Process memory on the worker thread; one downscaled preview copy for the UI | **Never** | **Never** |
| Landmarks / head angles | Memory, per frame | Never | Never (not logged) |
| Calibration baseline (6 medians + camera index + resolution + timestamp) | `%APPDATA%\PixelPosture\settings.json` | Never | Yes, until you choose *Forget calibration* |
| Settings | Same file | Never | Yes |
| Session statistics | Memory | Never | No |
| Logs (states, errors, timings) | `%APPDATA%\PixelPosture\logs\` (rotating, 3 × 1 MB) | Never | Yes |
| UI icon cache (two generated PNGs) | `%APPDATA%\PixelPosture\cache\icons\` | Never | Yes |

The desktop app makes **no network requests at runtime**. The only network access in the
whole project is `download_models.py`, which you run yourself. It fetches two files over
HTTPS from Google's official MediaPipe bucket and refuses them unless their SHA-256 hashes
match the pinned values.

## Camera controls

* The camera never starts at launch. Only **Start Monitoring** or **Calibrate** opens it.
* **Detect** briefly opens each camera index to see which ones work. The UI warns about this,
  and it only runs when you click the button.
* **Pause**, **Stop**, **Quit**, camera errors and Windows logoff all release the device.
  (Pause and Quit were verified on hardware: another process could reopen the camera
  immediately afterwards.)
* While monitoring is running, the app may reopen the same camera **once** by itself if it
  stops delivering frames (for example after sleep/resume). It never opens a camera when
  monitoring is paused, stopped or idle.
* Camera and monitoring status are shown in the header chips and the tray tooltip.
* The preview can be turned off. While the window is hidden, no preview images are produced
  at all.

## Threat model

| Threat | Mitigation | Residual risk |
|---|---|---|
| Video exfiltration | No network code in the runtime path; no frames written to disk | Other malware on the PC could read the camera itself; out of scope |
| Accidental recording | No recording feature exists; `.gitignore` excludes video files and capture folders | – |
| Silent camera use | Explicit start, visible status, release on pause | Windows' own camera indicator is the authoritative signal |
| Tampered model files | SHA-256 verification at download **and** at load time | Trust in Google's published models |
| Malformed settings file | Type checks, range clamping, corrupt file backed up and replaced by defaults | – |
| Duplicate instances fighting over the camera | Per-user single-instance guard (`QLocalServer`, user-only access) | – |
| Sensitive data in logs | Logs contain states and error messages only, never pixel data or landmark coordinates | Error messages may include the camera index |
| Over-trust in health advice | Clear "not a medical device" statements; experimental thresholds documented | Users may still over-interpret Pip |

## Website

The showcase website is static. It self-hosts its fonts, loads no analytics or third-party
scripts, sets no cookies, and never calls `getUserMedia`. The test suite asserts that the
demo page does not request camera access.

## Recommendations for users

* Allow camera access for desktop apps only as long as you use Pixel Posture.
* Use **Forget calibration** in Settings and delete `%APPDATA%\PixelPosture` to remove all
  stored data.
