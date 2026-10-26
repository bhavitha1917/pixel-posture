import { existsSync } from 'node:fs'
import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { parseRepoUrl } from './config'
import { DEMO_STEPS, nextStepIndex, STEP_MS } from './demo/script'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

const ROUTES = ['/', '/demo', '/docs', '/about']

describe('routing and navigation', () => {
  it.each(ROUTES)('renders %s with header, main heading and footer', (path) => {
    renderAt(path)
    expect(screen.getByRole('banner')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.getByRole('contentinfo')).toBeInTheDocument()
  })

  it('shows the hero headline and both CTAs on the home page', () => {
    renderAt('/')
    expect(screen.getByRole('heading', { level: 1, name: 'Sit comfy. Stay mindful.' })).toBeInTheDocument()
    const main = screen.getByRole('main')
    expect(within(main).getAllByRole('link', { name: 'Explore the Demo' })[0]).toHaveAttribute('href', '/demo')
    expect(within(main).getAllByRole('link', { name: 'Get Started' })[0]).toHaveAttribute('href', '/docs')
  })

  it('navigates between pages from the header', async () => {
    const user = userEvent.setup()
    renderAt('/')
    const nav = screen.getByRole('navigation', { name: 'Primary' })
    await user.click(within(nav).getByRole('link', { name: 'Get started' }))
    expect(screen.getByRole('heading', { level: 1, name: 'Install Pixel Posture' })).toBeInTheDocument()
    await user.click(within(nav).getByRole('link', { name: 'Explore the Demo' }))
    expect(screen.getByRole('heading', { level: 1, name: "Meet Pip's moods" })).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Pixel Posture home' }))
    expect(screen.getByRole('heading', { level: 1, name: 'Sit comfy. Stay mindful.' })).toBeInTheDocument()
  })

  it('toggles the mobile menu and closes it with Escape', async () => {
    const user = userEvent.setup()
    renderAt('/')
    const toggle = screen.getByRole('button', { name: 'Open menu' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await user.click(toggle)
    expect(screen.getByRole('button', { name: 'Close menu' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('navigation', { name: 'Primary' })).toHaveAttribute('data-open', 'true')
    await user.keyboard('{Escape}')
    expect(screen.getByRole('button', { name: 'Open menu' })).toHaveAttribute('aria-expanded', 'false')
    await user.click(screen.getByRole('button', { name: 'Open menu' }))
    await user.click(within(screen.getByRole('navigation', { name: 'Primary' })).getByRole('link', { name: 'About' }))
    expect(screen.getByRole('navigation', { name: 'Primary' })).toHaveAttribute('data-open', 'false')
  })

  it('shows a friendly 404 for unknown routes', () => {
    renderAt('/nope')
    expect(screen.getByRole('heading', { level: 1, name: 'Page not found' })).toBeInTheDocument()
  })
})

describe('internal links', () => {
  it.each(ROUTES)('every internal link on %s points to a real route or anchor', (path) => {
    const { container } = renderAt(path)
    const anchors = Array.from(container.querySelectorAll('a[href]'))
    for (const a of anchors) {
      const href = a.getAttribute('href') ?? ''
      if (/^https?:/.test(href)) continue
      if (href.startsWith('/licenses/')) {
        expect(existsSync(`public${href}`), `${path} → ${href}`).toBe(true)
        continue
      }
      if (href.startsWith('#')) {
        expect(container.querySelector(href), `${path} → ${href}`).not.toBeNull()
        continue
      }
      const [route, hash] = href.split('#')
      expect(ROUTES, `${path} → ${href}`).toContain(route)
      if (hash) {
        const { container: target } = renderAt(route)
        expect(target.querySelector(`#${hash}`), `${path} → ${href}`).not.toBeNull()
      }
    }
  })

  it('shows repository links as pending when no URL is configured', () => {
    renderAt('/')
    expect(screen.getAllByText('Repository link coming soon').length).toBeGreaterThan(0)
  })
})

describe('simulated demo', () => {
  let getUserMedia: ReturnType<typeof vi.fn>

  beforeEach(() => {
    getUserMedia = vi.fn()
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia },
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('is clearly labelled as simulated and never touches the camera', () => {
    renderAt('/demo')
    expect(screen.getByText(/Simulated Demo — no live posture detection/)).toBeInTheDocument()
    expect(screen.getByText(/All values below are scripted examples/)).toBeInTheDocument()
    expect(getUserMedia).not.toHaveBeenCalled()
  })

  it('switches states when a state button is pressed', async () => {
    const user = userEvent.setup()
    renderAt('/demo')
    await user.click(screen.getByRole('button', { name: 'Critical' }))
    expect(screen.getByRole('button', { name: 'Critical' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('heading', { name: 'Time for a reset' })).toBeInTheDocument()
    expect(screen.getByRole('note', { name: 'Example Windows notification' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Tracking unavailable' }))
    expect(screen.getByRole('heading', { name: 'Tracking unavailable' })).toBeInTheDocument()
    expect(screen.queryByRole('note', { name: 'Example Windows notification' })).toBeNull()
  })

  it('plays the scripted session step by step and stops at the end', () => {
    vi.useFakeTimers()
    renderAt('/demo')
    act(() => screen.getByRole('button', { name: 'Play scripted session' }).click())
    expect(screen.getByRole('button', { name: 'Pause script' })).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(STEP_MS))
    expect(screen.getByRole('button', { name: DEMO_STEPS[1].label })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('progressbar', { name: 'Scripted session progress' })).toHaveAttribute('aria-valuenow', '2')
    for (let i = 0; i < DEMO_STEPS.length; i++) act(() => vi.advanceTimersByTime(STEP_MS))
    const last = DEMO_STEPS[DEMO_STEPS.length - 1]
    expect(screen.getByRole('button', { name: last.label })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Play scripted session' })).toBeInTheDocument()
  })

  it('resets to the first step', async () => {
    const user = userEvent.setup()
    renderAt('/demo')
    await user.click(screen.getByRole('button', { name: 'Warning' }))
    await user.click(screen.getByRole('button', { name: 'Reset' }))
    expect(screen.getByRole('button', { name: DEMO_STEPS[0].label })).toHaveAttribute('aria-pressed', 'true')
  })
})

describe('demo script and config', () => {
  it('advances and ends', () => {
    expect(nextStepIndex(0)).toBe(1)
    expect(nextStepIndex(DEMO_STEPS.length - 1)).toBeNull()
  })

  it('covers all five pet states', () => {
    expect(new Set(DEMO_STEPS.map((s) => s.pet))).toEqual(
      new Set(['calibrating', 'thriving', 'warning', 'critical', 'unavailable']),
    )
  })

  it('accepts only https repository URLs', () => {
    expect(parseRepoUrl('https://github.com/me/pixel-posture/')).toBe('https://github.com/me/pixel-posture')
    expect(parseRepoUrl('  ')).toBeNull()
    expect(parseRepoUrl(undefined)).toBeNull()
    expect(parseRepoUrl('javascript:alert(1)')).toBeNull()
    expect(parseRepoUrl('http://example.com')).toBeNull()
  })
})
