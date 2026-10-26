import { useEffect } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { SiteFooter } from './components/SiteFooter'
import { SiteHeader } from './components/SiteHeader'
import { AboutPage } from './pages/AboutPage'
import { DemoPage } from './pages/DemoPage'
import { DocsPage } from './pages/DocsPage'
import { HomePage } from './pages/HomePage'
import { NotFoundPage } from './pages/NotFoundPage'

const TITLES: Record<string, string> = {
  '/': 'Pixel Posture: a gentle, local-first posture companion',
  '/demo': 'Simulated demo · Pixel Posture',
  '/docs': 'Get started · Pixel Posture',
  '/about': 'About · Pixel Posture',
}

/** Scroll to #hash targets after navigation (including from other pages), else to top. */
function ScrollManager() {
  const { pathname, hash } = useLocation()
  useEffect(() => {
    document.title = TITLES[pathname] ?? 'Page not found · Pixel Posture'
    if (hash) {
      const target = document.getElementById(decodeURIComponent(hash.slice(1)))
      if (target) {
        target.scrollIntoView?.()
        return
      }
    }
    window.scrollTo?.(0, 0)
  }, [pathname, hash])
  return null
}

export default function App() {
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <ScrollManager />
      <SiteHeader />
      <main id="main">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/demo" element={<DemoPage />} />
          <Route path="/docs" element={<DocsPage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
      <SiteFooter />
    </>
  )
}
