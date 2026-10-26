# Testing

## Strategy

| Layer | How it is tested | Hardware? |
|---|---|---|
| Geometry, calibration, smoothing, timers, state machine (`app/posture`) | Deterministic unit tests feeding **synthetic observations** into the real modules | No |
| Alert policy and delivery (`services/alerts.py`, `notifications.py`) | Real policy driven by the real engine. Only the OS boundary (notification backend, sound) is replaced by recording fakes | No |
| Settings (`settings/store.py`) | Round-trip, clamping, wrong types, corrupt-file backup | No |
| Lifecycle (`services/monitor.py`, `worker.py`) | Real `QThread` + controller + engine. Only the camera and model inference are faked | No |
| UI wiring (window, tray, dialog, application) | pytest-qt on the `offscreen` platform | No |
| Single instance | A real second **process** connects to the first | No |
| Vision pipeline with real models and camera | `python local-app/main.py --self-check`, plus manual runs | **Yes** |
| Camera outages (no stale state, reopen once, error on failure) | Lifecycle tests with a simulated camera that stops delivering frames | No |
| Sleep/resume timing (silent gaps) | `SignalTracker` regression test | No |
| Model assets and `--self-check` failure paths | Missing/corrupt model files in a temp folder | No |
| Website | Vitest + Testing Library (jsdom), `oxlint`, `tsc` (app + tests) + production build, and a headless-Chrome audit | No |

Hardware tests are deliberately kept out of `pytest`, so CI (which has no webcam) stays
deterministic.

## Commands

```powershell
# repository root, venv active
pytest
ruff check .
ruff format --check .
mypy
python local-app/main.py --self-check

# showcase/
npm run lint
npm test
npm run build
```

## Results (re-run during the stabilization audit, 2026-10-26; Windows 11, Python 3.11.9, Node 24.19)

| Command | Result |
|---|---|
| `pytest` | **134 passed**, 0 failed (≈12 s) |
| `ruff check .` | All checks passed |
| `ruff format --check .` | All files formatted |
| `mypy` (strict) | No issues in 35 source files |
| `npm run lint` | No warnings or errors |
| `npm ci` | Clean install from the lockfile; `npm audit --omit=dev`: 0 vulnerabilities |
| `npm test` | **20 passed**, 0 failed |
| `npm run build` | Succeeded (JS ≈300 kB, ≈95 kB gzipped) |
| `python local-app/main.py --self-check` | Exit 0: models verified and loaded; camera opened at 640×480; 30 frames analysed; camera released |
| PyInstaller build + `Start-Process PixelPosture.exe --self-check -Wait` | Build OK; exit code 0; results in the log; GUI start logged no warnings |
| Headless-Chrome audit (5 routes × 375/768/1280 px) | 0 issues: overflow, broken images, alt text, unnamed controls, console errors, failed requests, camera-API calls, contrast; focus visible; reduced motion respected |

### Hardware checks performed in the development session

These were run on the development laptop's real webcam. No frames were saved or viewed.

* The real `FrameAnalyzer` ran at ≈28 fps for both models together (uncapped). With a face
  visible but shoulders below the frame edge, the body was correctly reported as
  "Shoulders are outside the camera view" rather than guessed.
* The head-pitch sign convention was cross-checked live against an independent
  landmark-depth estimate. The two agreed in sign and moved together.
* End-to-end GUI run (preview disabled): Start, then calibration **succeeded** on live frames,
  then Thriving, at ≈11.7 results/s (12 fps cap). **Pause released the camera**: another
  `VideoCapture` opened it while paused. Resume restarted the worker. **Quit** left no worker
  and the camera could be reopened. The test notification was dispatched without error.
* Website: the production build was served locally and checked in Chrome. There were no
  console errors. Every route has no horizontal overflow at a 375 px viewport, and deep
  links and hash navigation work.

## Manual checklist (still required on your machine)

These need a person in front of the camera, or a visual check of Windows UI, and were
**not** verified automatically:

- [ ] Windows toast notifications visibly appear. Steps: (1) Windows Settings → System → Notifications: Notifications **On**, Do not disturb **Off**. (2) Start Pixel Posture → **Settings → Send test notification**. A toast titled "Pixel Posture test" should appear bottom-right, and in the notification centre (Win+N). (3) Close the main window (it goes to the tray), right-click Pip → Settings → Send test notification again. It should still appear. (4) Turn on Do not disturb and repeat. It should be suppressed (it may still land silently in the notification centre). If nothing appears, look for a "Python" or "PixelPosture" entry under Settings → System → Notifications and make sure it is allowed.
- [ ] The alert sound plays, and stops when *Sound* is off.
- [ ] Sitting upright for a few minutes keeps Pip **Thriving** with no notifications.
- [ ] Leaning toward the screen for more than 10 s triggers **Warning** and one notification. Sitting back recovers after about 3 s.
- [ ] Looking down at a phone or notes for more than 10 s triggers a head-tilt **Warning** independently of the back signal.
- [ ] Staying clearly slouched for more than 30 s escalates to **Critical**. A mild slouch stays at Warning.
- [ ] Leaving the frame shows **Tracking unavailable** within about 2 s and sends no posture notifications.
- [ ] Minimizing the window or closing it to the tray keeps notifications coming while you work in other apps.
- [ ] Tray menu: Open / Pause / Resume / Settings / Quit all behave as labelled, and the Windows camera indicator turns off on Pause and Quit.
- [ ] Launching a second copy brings the first window forward.
- [ ] Unplugging an external webcam while monitoring shows *Tracking unavailable* within about 2 s. After about 3 s the app tries to reopen it once, then shows a camera error, and the app stays responsive. Replugging and pressing **Try Again** resumes.
- [ ] Close the lid or sleep the laptop for a minute while monitoring. On resume, Pip should not jump straight to Warning/Critical, and monitoring continues (or shows a clear camera error with **Try Again**).
- [ ] A long session (1 hour or more) keeps memory and CPU stable (check Task Manager).
- [ ] The PyInstaller build (README §20) starts on a machine without Python.
