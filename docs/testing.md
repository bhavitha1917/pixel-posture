# Testing

## Strategy

| Layer | How it is tested | Hardware? |
|---|---|---|
| Geometry, calibration, smoothing, timers, state machine (`app/posture`) | Deterministic unit tests feeding **synthetic observations** into the real modules | No |
| Alert policy and delivery (`services/alerts.py`, `notifications.py`) | Real policy driven by the real engine. Only the OS boundary (notification backend, sound) is replaced by recording fakes | No |
| Shipped reminder timing (30 s / 60 s severe / 5 s / 60 s cooldown) | `test_default_timing.py`: brief vs sustained vs severe deviations, recovery, cooldown spacing, missing landmarks and sleep gaps, back/head independence, all on the real defaults | No |
| Settings (`settings/store.py`) | Round-trip, clamping, wrong types, corrupt-file backup, version-1 upgrade that keeps customised values | No |
| Pip's chime (`services/sound.py`) | Asset found, format and loudness, matches its generator, bundled by the spec; volume scaling, repeat guard, disabled sound, missing/corrupt/unsupported file → fallback. Playback is replaced by a recorder (silent) | No |
| Floating Pip (`ui/floating_pet.py`) | Window flags (tool, frameless, topmost, no focus), size, click-through mask, repaint only on change, menu per status, drag, multi-monitor placement, and the app lifecycle (close/minimize dashboard, hide/show from tray and settings, quit) on the `offscreen` platform | No |
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

## Results (re-run after adding floating Pip, gentler timing and the chime, 2026-10-27; Windows 11, Python 3.11.9, Node 24.19)

| Command | Result |
|---|---|
| `pytest` | **199 passed**, 0 failed (≈26 s) |
| `ruff check .` | All checks passed |
| `ruff format --check .` | All files formatted |
| `mypy` (strict) | No issues in 38 source files |
| `npm run lint` | No warnings or errors |
| `npm test` | **20 passed**, 0 failed |
| `npm run build` | Succeeded (JS ≈301 kB, ≈95 kB gzipped) |
| `python local-app/main.py --self-check` | Exit 0: models verified and loaded; camera opened; 30 frames analysed; camera released |
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
- [ ] **Pip's chime.** Settings → Reminders → **Preview sound**: a soft two-note chime (low then high) plays once. Move the volume slider to 20 % and preview again: quieter. 100 %: louder but not harsh. Click Preview several times quickly: chimes restart rather than pile up. Untick *Play Pip's chime*, Save, Send test notification: the toast appears with no chime. (Windows may add its own toast sound; that is controlled in Windows notification settings.)
- [ ] Sitting upright for a few minutes keeps Pip **Thriving** with no notifications.
- [ ] Leaning in or slouching for about **20 s** and then sitting up gives **no** Warning.
- [ ] Leaning toward the screen for more than **30 s** triggers **Warning** and one notification with the chime. Sitting back recovers after about **5–6 s**; sitting up for only 3 s and slouching again keeps the Warning.
- [ ] Looking down at a phone or notes for more than 30 s triggers a head-tilt **Warning** independently of the back signal.
- [ ] Staying **clearly** slouched for more than **60 s** escalates to **Critical**. A mild slouch stays at Warning however long it lasts. The second notification comes at least 60 s after the first.
- [ ] **Floating Pip.** Launch: a small Pip appears bottom-right above the taskbar. Click into VS Code or Chrome and type: Pip stays on top and typing is never interrupted. Click just beside Pip (inside its square but not on its pixels): the click reaches the app underneath. Drag Pip to another spot (and to a second monitor if you have one), quit and relaunch: it comes back there. Drag it half off a screen edge: it slides fully back on. Pip's face changes with Thriving / Warning / Critical; it shows Zs when paused or when you leave the frame.
- [ ] **Floating Pip menu.** Right-click Pip: Open Dashboard, Pause/Resume Monitoring, Hide Pip, Quit Pixel Posture all work. After Hide Pip, the tray menu's *Show Pip on Desktop* and the Quick settings checkbox bring it back. Close and minimize the dashboard: Pip stays and monitoring continues (camera light stays on). Quit from Pip: Pip, dashboard and tray icon disappear and the camera light turns off.
- [ ] Leaving the frame shows **Tracking unavailable** within about 2 s and sends no posture notifications.
- [ ] Minimizing the window or closing it to the tray keeps notifications coming while you work in other apps.
- [ ] Tray menu: Open / Pause / Resume / Settings / Quit all behave as labelled, and the Windows camera indicator turns off on Pause and Quit.
- [ ] Launching a second copy brings the first window forward.
- [ ] Unplugging an external webcam while monitoring shows *Tracking unavailable* within about 2 s. After about 3 s the app tries to reopen it once, then shows a camera error, and the app stays responsive. Replugging and pressing **Try Again** resumes.
- [ ] Close the lid or sleep the laptop for a minute while monitoring. On resume, Pip should not jump straight to Warning/Critical, and monitoring continues (or shows a clear camera error with **Try Again**).
- [ ] A long session (1 hour or more) keeps memory and CPU stable (check Task Manager).
- [ ] The PyInstaller build (README §20) starts on a machine without Python.
