import { Menu, X } from 'lucide-react'
import { type MouseEvent, useEffect, useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import logo from '../assets/pet/thriving-0.svg'

const LINKS = [
  { to: '/#features', label: 'Features', hash: true },
  { to: '/#how-it-works', label: 'How it works', hash: true },
  { to: '/#privacy', label: 'Privacy', hash: true },
  { to: '/docs', label: 'Get started', hash: false },
  { to: '/about', label: 'About', hash: false },
]

export function SiteHeader() {
  const [open, setOpen] = useState(false)
  // Close the mobile menu when any of its links is followed.
  const onNavClick = (event: MouseEvent<HTMLElement>) => {
    if ((event.target as HTMLElement).closest('a')) setOpen(false)
  }

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  return (
    <header className="site-header">
      <div className="container site-header__inner">
        <Link to="/" className="brand" aria-label="Pixel Posture home">
          <img src={logo} alt="" width={26} height={22} />
          <span>PIXEL POSTURE</span>
        </Link>
        <button
          type="button"
          className="menu-toggle"
          aria-expanded={open}
          aria-controls="primary-nav"
          aria-label={open ? 'Close menu' : 'Open menu'}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X size={22} aria-hidden /> : <Menu size={22} aria-hidden />}
        </button>
        <nav id="primary-nav" className="nav" data-open={open} aria-label="Primary" onClick={onNavClick}>
          {LINKS.map((link) =>
            link.hash ? (
              <Link key={link.to} to={link.to}>
                {link.label}
              </Link>
            ) : (
              <NavLink key={link.to} to={link.to}>
                {link.label}
              </NavLink>
            ),
          )}
          <Link to="/demo" className="btn btn--primary btn--small nav__cta">
            Explore the Demo
          </Link>
        </nav>
      </div>
    </header>
  )
}
