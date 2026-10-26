import { Link } from 'react-router-dom'
import { RepoLink } from '../components/RepoLink'

const STACK = [
  'Python 3.11',
  'PySide6 (Qt)',
  'MediaPipe Tasks',
  'OpenCV',
  'NumPy',
  'pytest',
  'React 19',
  'Vite',
  'TypeScript',
  'Lucide icons',
]

export function AboutPage() {
  return (
    <>
      <section className="page-head container">
        <span className="eyebrow">About</span>
        <h1>A kinder kind of reminder</h1>
        <p>
          Pixel Posture started from a simple observation: after a long study session, our necks
          told us what our screens had been doing to our posture, hours too late.
        </p>
      </section>

      <div className="container grid grid--2">
        <article className="card">
          <h2>Design philosophy</h2>
          <ul>
            <li>
              <strong>Local first.</strong> If a feature would need your video to leave your
              computer, we don't build it.
            </li>
            <li>
              <strong>Personal, not prescriptive.</strong> Your calibrated comfort is the
              reference, not a textbook angle.
            </li>
            <li>
              <strong>Patient.</strong> Duration, hysteresis and cooldowns keep reminders rare
              and meaningful.
            </li>
            <li>
              <strong>Honest.</strong> When the camera can't see you, Pip says so instead of
              guessing.
            </li>
          </ul>
        </article>
        <article className="card">
          <h2>Built with</h2>
          <ul className="tech">
            {STACK.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p className="muted" style={{ marginTop: 'var(--space-4)' }}>
            The desktop app is the product. This website is a separate static site that explains
            it. Its <Link to="/demo">demo</Link> is simulated.
          </p>
        </article>
        <article className="card">
          <h2>What might come next</h2>
          <ul>
            <li>Opt-in launch at login</li>
            <li>Gentle break reminders</li>
            <li>Calibration profiles for different desks</li>
            <li>A packaged installer with a proper Windows app identity</li>
            <li>An optional, local-only history chart</li>
          </ul>
          <p className="muted">These are ideas, not promises, and none of them exist yet.</p>
        </article>
        <article className="card">
          <h2>Not a medical device</h2>
          <p>
            Pixel Posture is a posture-awareness aid. It doesn't diagnose conditions, measure
            anatomy with clinical accuracy, or guarantee that it prevents injury. If you have
            pain, please talk to a health professional.
          </p>
          <p style={{ marginBottom: 0 }}>
            <RepoLink>Source code on GitHub</RepoLink>
          </p>
        </article>
        <article className="card">
          <h2>Credits & licenses</h2>
          <p>
            Pip is original pixel art. Fonts: Inter and Press Start 2P, both under the SIL Open
            Font License (<a href="/licenses/inter-OFL.txt">Inter license</a>,{' '}
            <a href="/licenses/press-start-2p-OFL.txt">Press Start 2P license</a>). Icons by
            Lucide (ISC). Pose and face models by Google MediaPipe (Apache-2.0), used only by
            the desktop app.
          </p>
        </article>
      </div>
    </>
  )
}
