import { useEffect, useState } from 'react'
import calibrating0 from '../assets/pet/calibrating-0.svg'
import calibrating1 from '../assets/pet/calibrating-1.svg'
import critical0 from '../assets/pet/critical-0.svg'
import critical1 from '../assets/pet/critical-1.svg'
import thriving0 from '../assets/pet/thriving-0.svg'
import thriving1 from '../assets/pet/thriving-1.svg'
import unavailable0 from '../assets/pet/unavailable-0.svg'
import unavailable1 from '../assets/pet/unavailable-1.svg'
import warning0 from '../assets/pet/warning-0.svg'
import warning1 from '../assets/pet/warning-1.svg'
import { usePrefersReducedMotion } from '../hooks'

/** The same five states as the desktop app; SVGs are exported from local-app sprites.py. */
export type PetState = 'calibrating' | 'thriving' | 'warning' | 'critical' | 'unavailable'

const FRAMES: Record<PetState, [string, string]> = {
  calibrating: [calibrating0, calibrating1],
  thriving: [thriving0, thriving1],
  warning: [warning0, warning1],
  critical: [critical0, critical1],
  unavailable: [unavailable0, unavailable1],
}

const DESCRIPTIONS: Record<PetState, string> = {
  calibrating: 'Pip looking curious',
  thriving: 'Pip smiling happily',
  warning: 'Pip looking a little concerned',
  critical: 'Pip looking tired and slumped',
  unavailable: 'Pip resting with eyes closed',
}

const FRAME_MS = 450

interface Props {
  state: PetState
  animate?: boolean
  className?: string
  /** Decorative sprites (next to text that already says the state) pass an empty label. */
  label?: string
}

export function PetSprite({ state, animate = true, className = 'pet', label }: Props) {
  const reducedMotion = usePrefersReducedMotion()
  const [frame, setFrame] = useState(0)
  const moving = animate && !reducedMotion

  useEffect(() => {
    if (!moving) return
    const id = window.setInterval(() => setFrame((f) => (f + 1) % 2), FRAME_MS)
    return () => window.clearInterval(id)
  }, [moving])

  return (
    <img
      className={className}
      src={FRAMES[state][moving ? frame : 0]}
      alt={label ?? DESCRIPTIONS[state]}
      width={26}
      height={22}
      draggable={false}
    />
  )
}
