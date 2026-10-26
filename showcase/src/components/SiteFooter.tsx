import { Link } from 'react-router-dom'
import { RepoLink } from './RepoLink'

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="container site-footer__inner">
        <div>
          <h2>Pixel Posture</h2>
          <p>
            Your posture. Your pixel pal. Your gentle reminder. A posture-awareness aid, not a
            medical device.
          </p>
          <p>Open source under the MIT License.</p>
        </div>
        <nav aria-label="Site">
          <h2>Explore</h2>
          <ul>
            <li>
              <Link to="/demo">Simulated demo</Link>
            </li>
            <li>
              <Link to="/#features">Features</Link>
            </li>
            <li>
              <Link to="/#how-it-works">How it works</Link>
            </li>
            <li>
              <Link to="/about">About</Link>
            </li>
          </ul>
        </nav>
        <nav aria-label="Project">
          <h2>Project</h2>
          <ul>
            <li>
              <Link to="/docs">Get started</Link>
            </li>
            <li>
              <RepoLink>GitHub repository</RepoLink>
            </li>
            <li>
              <RepoLink kind="readme">Full README</RepoLink>
            </li>
          </ul>
        </nav>
      </div>
    </footer>
  )
}
