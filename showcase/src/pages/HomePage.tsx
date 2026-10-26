import {
  Activity,
  BellRing,
  CircleCheck,
  Crosshair,
  EyeOff,
  Gauge,
  Heart,
  MonitorSmartphone,
  ScanFace,
  ShieldCheck,
  Timer,
  TriangleAlert,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { type PetState, PetSprite } from '../components/PetSprite'
import { RepoLink } from '../components/RepoLink'

interface Feature {
  icon: ReactNode
  tone?: 'mint' | 'peach' | 'coral'
  title: string
  body: string
}

const FEATURES: Feature[] = [
  {
    icon: <Activity size={22} />,
    title: 'Continuous local monitoring',
    body: 'Runs on a background thread at about 12 frames per second while you work in other apps.',
  },
  {
    icon: <Gauge size={22} />,
    tone: 'mint',
    title: 'Back & shoulder estimation',
    body: 'Combines four body-landmark signals: leaning in, hunching, sinking and side lean.',
  },
  {
    icon: <ScanFace size={22} />,
    tone: 'mint',
    title: 'Downward head-tilt estimation',
    body: 'A separate head-pose signal from MediaPipe Face Landmarker, tracked on its own timer.',
  },
  {
    icon: <Crosshair size={22} />,
    title: 'Personal calibration',
    body: 'Learns your comfortable posture from many stable frames, instead of one "correct" angle for everyone.',
  },
  {
    icon: <Timer size={22} />,
    tone: 'peach',
    title: 'Duration-based alerts',
    body: 'Brief movements are ignored. Reminders come only when a deviation lasts, with hysteresis and recovery checks.',
  },
  {
    icon: <BellRing size={22} />,
    tone: 'peach',
    title: 'Native notifications',
    body: 'Windows notifications with a configurable cooldown and no repeats for the same ongoing issue.',
  },
  {
    icon: <MonitorSmartphone size={22} />,
    title: 'System-tray operation',
    body: 'Close or minimize the window and Pip keeps watch from the tray: pause, resume or quit from there.',
  },
  {
    icon: <Heart size={22} />,
    tone: 'coral',
    title: 'Pixel-pet feedback',
    body: 'Pip mirrors your posture state with gentle, non-shaming messages.',
  },
  {
    icon: <ShieldCheck size={22} />,
    tone: 'mint',
    title: 'Privacy-conscious by design',
    body: 'Frames stay in memory on your PC. No uploads, no recordings, no accounts.',
  },
]

const PIPELINE = [
  {
    title: 'Webcam',
    body: 'OpenCV captures frames after you press Start. Nothing is written to disk.',
    where: 'worker thread',
  },
  {
    title: 'Landmark detection',
    body: 'MediaPipe finds shoulders and ears, plus a face mesh with a head-pose matrix.',
    where: 'worker thread',
  },
  {
    title: 'Posture estimation',
    body: 'Features are compared with your calibrated baseline and scaled by your tolerance.',
    where: 'pure Python',
  },
  {
    title: 'Filtering & states',
    body: 'Time-based smoothing, hysteresis and per-signal timers drive the pet state machine.',
    where: 'pure Python',
  },
  {
    title: 'Pet & notifications',
    body: 'The dashboard, tray icon and rate-limited Windows notifications update.',
    where: 'UI thread',
  },
]

const STATES: { state: PetState; title: string; body: string }[] = [
  { state: 'calibrating', title: 'Calibrating', body: 'Learning your comfortable posture.' },
  { state: 'thriving', title: 'Thriving', body: 'Within your usual range.' },
  { state: 'warning', title: 'Warning', body: 'A deviation has lasted ~10 s.' },
  { state: 'critical', title: 'Critical', body: 'Clearly larger, for ~30 s.' },
  { state: 'unavailable', title: 'Unavailable', body: "Can't see you clearly." },
]

export function HomePage() {
  return (
    <>
      <section className="hero">
        <div className="container hero__grid">
          <div>
            <span className="eyebrow">Posture companion for Windows</span>
            <h1>Sit comfy. Stay mindful.</h1>
            <p className="hero__lead">
              Pixel Posture watches for long stretches of slouching or head-down posture using
              your webcam, entirely on your own computer. Pip, your pixel pal, gives you a
              gentle nudge when it's time to reset.
            </p>
            <div className="hero__actions">
              <Link to="/demo" className="btn btn--primary">
                Explore the Demo
              </Link>
              <Link to="/docs" className="btn btn--secondary">
                Get Started
              </Link>
            </div>
            <p className="hero__note">
              <EyeOff size={16} aria-hidden /> This website never accesses your camera.
            </p>
          </div>
          <div className="hero__art">
            <PetSprite state="thriving" />
            <p className="hero__bubble">
              <strong>Pip:</strong> "Looking good! Your posture is within your usual range."
            </p>
          </div>
        </div>
      </section>

      <section className="section section--tint" aria-labelledby="preview-heading">
        <div className="container">
          <div className="section-head">
            <span className="eyebrow">The desktop app</span>
            <h2 id="preview-heading">A calm dashboard that you can minimize</h2>
            <p>
              Pip, two separate posture signals, an optional camera preview and your session
              summary in one window. Close it and monitoring continues from the tray.
            </p>
          </div>
          <div className="grid grid--2">
            <figure className="screenshot">
              <img
                src="/screenshots/dashboard-launch.webp"
                alt="Pixel Posture dashboard at launch: Pip, Start Monitoring button, camera-off instructions and empty signal panels"
                width={1200}
                height={815}
                loading="lazy"
              />
              <figcaption>Actual screenshot of the app at launch. The camera stays off until you press Start.</figcaption>
            </figure>
            <figure className="screenshot">
              <img
                src="/screenshots/dashboard-example.webp"
                alt="Pixel Posture dashboard in the Warning state: Pip looks concerned, head tilt shows Warning, back and shoulders within range"
                width={1200}
                height={815}
                loading="lazy"
              />
              <figcaption>
                The real app window showing a Warning, rendered with scripted example observations
                (not a live measurement). Preview hidden for privacy.
              </figcaption>
            </figure>
          </div>
        </div>
      </section>

      <section className="section" aria-labelledby="problem-heading">
        <div className="container">
          <div className="section-head">
            <span className="eyebrow">Why</span>
            <h2 id="problem-heading">Laptops pull us forward without us noticing</h2>
            <p>
              Low screens invite a dropped head and rounded shoulders, and hours can pass before
              you notice. Most reminders either nag constantly or need your video in the cloud.
            </p>
          </div>
          <div className="split">
            <div className="card">
              <h3>The problem</h3>
              <ul>
                <li>Posture drifts slowly, so you rarely notice it happening.</li>
                <li>Timer-based reminders ignore what you're actually doing.</li>
                <li>Camera-based tools often upload video or demand an account.</li>
                <li>Alerts on every small movement quickly get muted.</li>
              </ul>
            </div>
            <div className="card">
              <h3>Pixel Posture's approach</h3>
              <ul>
                <li>Compares you with your own calibrated, comfortable posture.</li>
                <li>Ignores brief movements and reminds you only about sustained deviations.</li>
                <li>Processes every frame locally and keeps nothing but a few numbers.</li>
                <li>Gives feedback through a friendly pet, never through shaming.</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section id="features" className="section section--tint" aria-labelledby="features-heading">
        <div className="container">
          <div className="section-head">
            <span className="eyebrow">Features</span>
            <h2 id="features-heading">Everything a gentle reminder needs</h2>
          </div>
          <div className="grid grid--3">
            {FEATURES.map((f) => (
              <article key={f.title} className="card feature">
                <span className={`icon-badge ${f.tone ? `icon-badge--${f.tone}` : ''}`} aria-hidden>
                  {f.icon}
                </span>
                <h3>{f.title}</h3>
                <p>{f.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="section" aria-labelledby="how-heading">
        <div className="container">
          <div className="section-head">
            <span className="eyebrow">How it works</span>
            <h2 id="how-heading">From webcam frame to gentle nudge</h2>
            <p>
              Five stages, all on your computer. Capture and inference run on a worker thread so
              the window stays responsive. Posture logic is plain, unit-tested Python.
            </p>
          </div>
          <ol className="pipeline">
            {PIPELINE.map((p) => (
              <li key={p.title} className="card">
                <h3>{p.title}</h3>
                <p>{p.body}</p>
                <span className="pipeline__where">{p.where}</span>
              </li>
            ))}
          </ol>

          <h3>Pip's five states</h3>
          <div className="states" style={{ marginBottom: 'var(--space-6)' }}>
            {STATES.map((s) => (
              <div key={s.state} className={`state-card tint-${s.state}`}>
                <PetSprite state={s.state} animate={false} label="" />
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </div>
            ))}
          </div>

          <div className="callout">
            <h3>
              <TriangleAlert size={20} aria-hidden /> Honest limitations
            </h3>
            <ul>
              <li>
                A single 2D webcam can't see your spine. The signals are relative proxies, not
                clinical angles.
              </li>
              <li>
                Hair over the ears, low light, or being partly out of frame lowers reliability.
                The app then says "tracking unavailable" rather than guessing.
              </li>
              <li>Moving the laptop or changing the screen angle requires recalibration.</li>
              <li>
                Thresholds are experimental defaults. Pixel Posture is an awareness aid, not a
                medical device.
              </li>
            </ul>
          </div>
        </div>
      </section>

      <section id="privacy" className="section section--tint" aria-labelledby="privacy-heading">
        <div className="container privacy">
          <div>
            <span className="eyebrow">Privacy first</span>
            <h2 id="privacy-heading">Your camera feed never leaves your PC</h2>
            <p className="muted">
              Pixel Posture analyses frames in memory and throws them away. The only things it
              saves are your settings and a handful of calibration numbers.
            </p>
          </div>
          <ul className="checklist card">
            {[
              'No uploads, no cloud processing, no telemetry or analytics.',
              'No video or images are ever saved.',
              'The camera only starts when you press Start or Calibrate.',
              'Pause, Stop and Quit release the camera immediately.',
              'Camera and monitoring status are always visible.',
              'This website loads no trackers and never requests camera access.',
            ].map((item) => (
              <li key={item}>
                <CircleCheck size={20} aria-hidden />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="cta">
            <PetSprite state="calibrating" label="" />
            <h2>Ready to meet Pip?</h2>
            <p>
              Try the simulated demo in your browser, or install the desktop app on Windows. Free
              and open source.
            </p>
            <div className="hero__actions">
              <Link to="/demo" className="btn btn--primary">
                Explore the Demo
              </Link>
              <Link to="/docs" className="btn btn--secondary">
                Get Started
              </Link>
            </div>
            <p style={{ marginTop: 'var(--space-4)', marginBottom: 0 }}>
              <RepoLink>View the source on GitHub</RepoLink>
            </p>
          </div>
        </div>
      </section>
    </>
  )
}
