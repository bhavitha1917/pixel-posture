import { FlaskConical, Pause, Play, RotateCcw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import notifyIcon from '../assets/pet/thriving-0.svg'
import { PetSprite } from '../components/PetSprite'
import {
  DEMO_STEPS,
  type ExampleSignal,
  LEVEL_LABELS,
  nextStepIndex,
  PET_TINTS,
  STEP_MS,
} from '../demo/script'

const SCALE_MAX = 2
const FILL: Record<ExampleSignal['level'], string> = {
  unavailable: 'var(--neutral)',
  ok: 'var(--mint-text)',
  drifting: 'var(--lavender-deep)',
  warning: '#d88a4e',
  critical: '#d65b4f',
}

function Meter({ name, signal }: { name: string; signal: ExampleSignal }) {
  const pct = signal.severity === null ? 0 : (Math.min(signal.severity, SCALE_MAX) / SCALE_MAX) * 100
  const issue = signal.issueSeconds > 0 ? `Example issue duration: ${signal.issueSeconds} s` : ''
  return (
    <div className="meter">
      <div className="meter__head">
        <strong>{name}</strong>
        <span className={`pill pill--${signal.level}`}>{LEVEL_LABELS[signal.level]}</span>
      </div>
      <div
        className="meter__track"
        role="img"
        aria-label={
          signal.severity === null
            ? `${name}: not measured in this example`
            : `${name}: example deviation ${signal.severity.toFixed(1)} times the tolerance`
        }
      >
        <div className="meter__fill" style={{ width: `${pct}%`, background: FILL[signal.level] }} />
        <div className="meter__marker" />
      </div>
      <div className="meter__scale" aria-hidden>
        <span>baseline</span>
        <span>tolerance</span>
        <span>2×</span>
      </div>
      {issue && <p className="muted" style={{ margin: '6px 0 0', fontSize: '0.88rem' }}>{issue}</p>}
    </div>
  )
}

export function DemoPage() {
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const step = DEMO_STEPS[index]

  useEffect(() => {
    if (!playing) return
    const id = window.setTimeout(() => {
      const next = nextStepIndex(index)
      if (next === null) setPlaying(false)
      else setIndex(next)
    }, STEP_MS)
    return () => window.clearTimeout(id)
  }, [playing, index])

  const select = (i: number) => {
    setPlaying(false)
    setIndex(i)
  }

  const togglePlay = () => {
    if (!playing && nextStepIndex(index) === null) setIndex(0)
    setPlaying((p) => !p)
  }

  return (
    <>
      <section className="page-head container">
        <span className="eyebrow">Interactive demo</span>
        <h1>Meet Pip's moods</h1>
        <p>
          Step through the states the desktop app uses, or play a short scripted session. This
          page never asks for your camera and does no posture detection. Real detection happens
          only in the Windows desktop app, on your own PC.
        </p>
      </section>

      <section className="container" aria-labelledby="demo-heading">
        <h2 id="demo-heading" className="visually-hidden">
          Simulated dashboard
        </h2>
        <div className="sim-banner" role="note">
          <FlaskConical size={20} aria-hidden />
          Simulated Demo — no live posture detection
          <span>All values below are scripted examples.</span>
        </div>

        <div className="demo">
          <div className="card">
            <div className={`demo__pet ${PET_TINTS[step.pet]}`}>
              <PetSprite state={step.pet} label="" />
            </div>
            <div aria-live="polite">
              <h3 className="demo__state-title">{step.title}</h3>
              <p>{step.message}</p>
            </div>
            <div className="demo__controls">
              <button type="button" className="btn btn--primary btn--small" onClick={togglePlay}>
                {playing ? <Pause size={16} aria-hidden /> : <Play size={16} aria-hidden />}
                {playing ? 'Pause script' : 'Play scripted session'}
              </button>
              <button type="button" className="btn btn--secondary btn--small" onClick={() => select(0)}>
                <RotateCcw size={16} aria-hidden />
                Reset
              </button>
            </div>
            <div
              className="timeline"
              role="progressbar"
              aria-label="Scripted session progress"
              aria-valuemin={1}
              aria-valuemax={DEMO_STEPS.length}
              aria-valuenow={index + 1}
              aria-valuetext={`Step ${index + 1} of ${DEMO_STEPS.length}: ${step.label}`}
            >
              {DEMO_STEPS.map((s, i) => (
                <span key={s.id} data-done={i <= index} />
              ))}
            </div>
          </div>

          <div className="card">
            <h3>Choose a state</h3>
            <div className="state-buttons" role="group" aria-label="Example states">
              {DEMO_STEPS.map((s, i) => (
                <button key={s.id} type="button" aria-pressed={i === index} onClick={() => select(i)}>
                  {s.label}
                </button>
              ))}
            </div>

            <h3 style={{ marginTop: 'var(--space-5)' }}>Example signals</h3>
            <Meter name="Back & shoulders" signal={step.back} />
            <Meter name="Head tilt" signal={step.head} />

            <h3>Example notification</h3>
            {step.notification ? (
              <div className="toast" role="note" aria-label="Example Windows notification">
                <img src={notifyIcon} alt="" width={26} height={22} />
                <div>
                  <span className="toast__label">Example · Pixel Posture</span>
                  <strong>{step.notification.title}</strong>
                  <p>{step.notification.message}</p>
                </div>
              </div>
            ) : (
              <p className="muted">
                No notification in this state. The desktop app only notifies when an issue lasts
                long enough, and never more often than your cooldown allows.
              </p>
            )}
          </div>
        </div>

        <div className="callout callout--lavender" style={{ marginTop: 'var(--space-5)' }}>
          <h3>How the real app decides</h3>
          <p style={{ margin: 0 }}>
            The desktop app uses your webcam and MediaPipe, locally, and compares live landmark
            estimates with your own calibrated baseline. It
            warns after about 30 seconds of sustained deviation, escalates only if a clearly
            larger deviation lasts about 60 seconds, and needs 5 seconds of
            improvement before it counts as recovered. Reminders come at most once a minute by default,
            with Pip&apos;s chime, and a floating Pip can show the state on your desktop.{' '}
            <Link to="/#how-it-works">See the
            pipeline</Link> or <Link to="/docs">install the app</Link>.
          </p>
        </div>
      </section>
    </>
  )
}
