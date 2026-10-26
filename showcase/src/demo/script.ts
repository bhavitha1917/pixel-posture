/**
 * Scripted example states for the SIMULATED website demo.
 *
 * Nothing here is measured. The values illustrate how the desktop app presents each state;
 * titles and messages are copied from the desktop app (local-app/app/posture/engine.py).
 */
import type { PetState } from '../components/PetSprite'

export type Level = 'unavailable' | 'ok' | 'drifting' | 'warning' | 'critical'

export interface ExampleSignal {
  level: Level
  /** Example deviation relative to tolerance (1.0 = edge of tolerance). Null = not measured. */
  severity: number | null
  /** Example duration of the ongoing issue, in seconds. */
  issueSeconds: number
}

export interface DemoStep {
  id: string
  label: string
  pet: PetState
  title: string
  message: string
  back: ExampleSignal
  head: ExampleSignal
  notification?: { title: string; message: string }
}

const none: ExampleSignal = { level: 'unavailable', severity: null, issueSeconds: 0 }

export const DEMO_STEPS: DemoStep[] = [
  {
    id: 'calibrating',
    label: 'Calibrating',
    pet: 'calibrating',
    title: "Let's get to know you",
    message: 'Hold still for a moment while I learn your comfortable position.',
    back: none,
    head: none,
  },
  {
    id: 'thriving',
    label: 'Thriving',
    pet: 'thriving',
    title: 'Thriving',
    message: 'Looking good! Your posture is within your usual range.',
    back: { level: 'ok', severity: 0.25, issueSeconds: 0 },
    head: { level: 'ok', severity: 0.15, issueSeconds: 0 },
  },
  {
    id: 'drifting',
    label: 'Brief change',
    pet: 'thriving',
    title: 'Thriving',
    message: 'Noticing a small change. No worries yet.',
    back: { level: 'ok', severity: 0.3, issueSeconds: 0 },
    head: { level: 'drifting', severity: 1.2, issueSeconds: 4 },
  },
  {
    id: 'warning',
    label: 'Warning',
    pet: 'warning',
    title: 'Posture check',
    message: 'Your head has been tilted downward for a while. Take a moment to reset.',
    back: { level: 'ok', severity: 0.35, issueSeconds: 0 },
    head: { level: 'warning', severity: 1.25, issueSeconds: 12 },
    notification: {
      title: 'Time for a posture check!',
      message: 'Your head has been tilted downward for a while. Take a moment to reset.',
    },
  },
  {
    id: 'critical',
    label: 'Critical',
    pet: 'critical',
    title: 'Time for a reset',
    message: "You've been leaning forward for a while. Try returning to a comfortable position.",
    back: { level: 'critical', severity: 1.7, issueSeconds: 34 },
    head: { level: 'warning', severity: 1.2, issueSeconds: 26 },
    notification: {
      title: "It's been a while. Time for a quick reset",
      message: "You've been leaning forward for a while. Try returning to a comfortable position.",
    },
  },
  {
    id: 'recovered',
    label: 'Recovered',
    pet: 'thriving',
    title: 'Thriving',
    message: 'Nice recovery! Your posture is back within your usual range.',
    back: { level: 'ok', severity: 0.4, issueSeconds: 0 },
    head: { level: 'ok', severity: 0.3, issueSeconds: 0 },
  },
  {
    id: 'unavailable',
    label: 'Tracking unavailable',
    pet: 'unavailable',
    title: 'Tracking unavailable',
    message: "I can't see you clearly. Make sure your face and both shoulders are in view.",
    back: none,
    head: none,
  },
]

/** Milliseconds each step is shown during "Play scripted session". */
export const STEP_MS = 2600

export function nextStepIndex(index: number): number | null {
  return index + 1 < DEMO_STEPS.length ? index + 1 : null
}

export const LEVEL_LABELS: Record<Level, string> = {
  unavailable: 'Not measured',
  ok: 'Within range',
  drifting: 'Drifting',
  warning: 'Warning',
  critical: 'Critical',
}

export const PET_TINTS: Record<PetState, string> = {
  calibrating: 'tint-calibrating',
  thriving: 'tint-thriving',
  warning: 'tint-warning',
  critical: 'tint-critical',
  unavailable: 'tint-unavailable',
}
