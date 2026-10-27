import { CodeBlock } from '../components/CodeBlock'
import { RepoLink } from '../components/RepoLink'
import { REPO_URL } from '../config'

// Commands mirror the root README (sections 13-16); keep them in sync.
const GET_SOURCE = REPO_URL
  ? `git clone ${REPO_URL}.git Pixel_Posture`
  : '# Download or clone the Pixel Posture source code, then:'
const INSTALL = `${GET_SOURCE}
cd Pixel_Posture
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt`

const MODELS = 'python local-app/scripts/download_models.py'
const LAUNCH = `.\\.venv\\Scripts\\Activate.ps1
python local-app/main.py`
const SELF_CHECK = 'python local-app/main.py --self-check'

const SECTIONS = [
  ['requirements', 'Requirements'],
  ['install', 'Install'],
  ['launch', 'Launch'],
  ['calibrate', 'Calibrate'],
  ['background', 'Background, tray & floating Pip'],
  ['settings', 'Settings'],
  ['troubleshooting', 'Troubleshooting'],
  ['privacy-notes', 'Privacy'],
] as const

const TROUBLESHOOTING: [string, string][] = [
  ['"Model files missing" banner', `Run ${MODELS}, then restart the app.`],
  [
    '"Camera could not be opened"',
    'Close other apps using the camera (Teams, Zoom, browser tabs), allow desktop apps in Windows Settings → Privacy & security → Camera, or pick another camera and press Detect.',
  ],
  [
    'Camera on but "Tracking unavailable"',
    'Make sure your face and both shoulders are visible and the room is lit. Sitting a little further back usually helps.',
  ],
  ['Calibration says "too much movement"', 'Rest your arms and hold still for about five seconds.'],
  [
    'No Windows notifications',
    'Turn off Do Not Disturb / Focus and allow notifications for Python (or PixelPosture.exe) in Settings → System → Notifications. Use Settings → Send test notification.',
  ],
  ['Tray icon not visible', 'Look in the taskbar overflow (^) and drag Pip onto the taskbar.'],
  [
    'Floating Pip is gone',
    'Turn on Show Pip on Desktop in the tray menu, in Quick settings, or in Settings → App.',
  ],
]

export function DocsPage() {
  return (
    <>
      <section className="page-head container">
        <span className="eyebrow">Get started</span>
        <h1>Install Pixel Posture</h1>
        <p>
          Pixel Posture runs from source with Python on Windows. Setup takes about five minutes,
          most of it downloading dependencies. There is no prebuilt download yet.
        </p>
      </section>

      <div className="container docs">
        <nav className="docs__toc" aria-label="On this page">
          <ul>
            {SECTIONS.map(([id, label]) => (
              <li key={id}>
                <a href={`#${id}`}>{label}</a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="docs__body">
          <section id="requirements">
            <h2>Requirements</h2>
            <ul>
              <li>Windows 10 or 11 (64-bit). Other platforms are untested.</li>
              <li>
                Python 3.11 from <a href="https://www.python.org/downloads/">python.org</a>.
                Check with <code>python --version</code>.
              </li>
              <li>A webcam that can see your face and both shoulders</li>
              <li>About 1 GB of disk space for dependencies</li>
            </ul>
          </section>

          <section id="install">
            <h2>Install</h2>
            <p>In PowerShell, clone the repository and create a virtual environment:</p>
            <CodeBlock label="install commands" code={INSTALL} />
            <p>Download the two MediaPipe models (about 10 MB, verified by SHA-256):</p>
            <CodeBlock label="model download command" code={MODELS} />
            <p className="muted">
              If PowerShell blocks <code>Activate.ps1</code>, run{' '}
              <code>Set-ExecutionPolicy -Scope CurrentUser RemoteSigned</code> once.
            </p>
          </section>

          <section id="launch">
            <h2>Launch</h2>
            <CodeBlock label="launch commands" code={LAUNCH} />
            <p>
              Optional: check models and camera without the window. It analyses about 30 frames,
              prints only counts, and releases the camera.
            </p>
            <CodeBlock label="self-check command" code={SELF_CHECK} />
          </section>

          <section id="calibrate">
            <h2>Calibrate</h2>
            <ol>
              <li>Sit comfortably upright the way you'd like to work.</li>
              <li>
                Press <strong>Start Monitoring</strong>. The first start calibrates
                automatically; use <strong>Calibrate</strong> any time afterwards.
              </li>
              <li>Hold still for a few seconds while the progress bar fills.</li>
              <li>
                Calibration succeeds only with at least 25 clear, stable frames showing both your
                face and shoulders. Otherwise it explains what to fix and saves nothing.
              </li>
            </ol>
            <p>Recalibrate after moving your laptop, changing the screen angle or switching camera.</p>
          </section>

          <section id="background">
            <h2>Background monitoring, the tray & floating Pip</h2>
            <ul>
              <li>Minimizing or switching apps does not stop monitoring.</li>
              <li>
                Closing the window hides it to the system tray (look in the <code>^</code> overflow
                area). You can change this in Settings to ask before quitting instead.
              </li>
              <li>
                Right-click Pip's tray icon for <strong>Open</strong>, <strong>Pause</strong> /{' '}
                <strong>Resume</strong>, <strong>Show Pip on Desktop</strong>,{' '}
                <strong>Settings</strong> and <strong>Quit</strong>.
              </li>
              <li>
                A small <strong>floating Pip</strong> sits on top of your other windows (bottom-right
                at first) and shows your posture state. It never takes keyboard focus, and clicks
                next to it go to the app underneath.
              </li>
              <li>
                Drag floating Pip anywhere; the spot is remembered. Double-click it to open the
                dashboard, or right-click it for <strong>Open Dashboard</strong>,{' '}
                <strong>Pause</strong> / <strong>Resume</strong>, <strong>Hide Pip</strong> and{' '}
                <strong>Quit</strong>. Bring a hidden Pip back from the tray menu or Quick
                settings.
              </li>
              <li>Pause turns the camera off. Quit stops everything and releases the camera.</li>
            </ul>
          </section>

          <section id="settings">
            <h2>Settings</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Setting</th>
                    <th scope="col">Default</th>
                    <th scope="col">What it does</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Sensitivity</td>
                    <td>Balanced</td>
                    <td>Relaxed / Balanced / Strict scale every tolerance (×1.35 / ×1 / ×0.75).</td>
                  </tr>
                  <tr>
                    <td>Warning after</td>
                    <td>30 s</td>
                    <td>How long a deviation must last before a warning.</td>
                  </tr>
                  <tr>
                    <td>Critical after</td>
                    <td>60 s</td>
                    <td>How long a clearly larger deviation must last before escalating.</td>
                  </tr>
                  <tr>
                    <td>Recovery confirmation</td>
                    <td>5 s</td>
                    <td>Sustained improvement needed before Pip relaxes.</td>
                  </tr>
                  <tr>
                    <td>Notification gap</td>
                    <td>60 s</td>
                    <td>Minimum time between Windows notifications.</td>
                  </tr>
                  <tr>
                    <td>Sound</td>
                    <td>On</td>
                    <td>
                      Pip&apos;s own two-note chime with reminders. Volume 70% by default, with a
                      Preview sound button.
                    </td>
                  </tr>
                  <tr>
                    <td>Floating Pip</td>
                    <td>On</td>
                    <td>Show Pip on top of other windows. Also in the tray menu and Quick settings.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section id="troubleshooting">
            <h2>Troubleshooting</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Symptom</th>
                    <th scope="col">Fix</th>
                  </tr>
                </thead>
                <tbody>
                  {TROUBLESHOOTING.map(([symptom, fix]) => (
                    <tr key={symptom}>
                      <td>{symptom}</td>
                      <td>{fix}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section id="privacy-notes">
            <h2>Privacy</h2>
            <p>
              Frames are analysed in memory and discarded. Nothing is uploaded and no video or
              images are saved. Only your settings and calibration numbers are stored, in{' '}
              <code>%APPDATA%\PixelPosture</code>. The app makes no network requests while running.
            </p>
            <p>
              <RepoLink kind="readme">Read the full README on GitHub</RepoLink>
            </p>
          </section>
        </div>
      </div>
    </>
  )
}
