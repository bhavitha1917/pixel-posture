import { Link } from 'react-router-dom'
import { PetSprite } from '../components/PetSprite'

export function NotFoundPage() {
  return (
    <section className="page-head container" style={{ textAlign: 'center' }}>
      <div style={{ width: 120, margin: '0 auto var(--space-4)' }}>
        <PetSprite state="unavailable" label="" />
      </div>
      <h1>Page not found</h1>
      <p style={{ margin: '0 auto var(--space-5)' }}>Pip looked everywhere but couldn't find it.</p>
      <Link to="/" className="btn btn--primary">
        Back to home
      </Link>
    </section>
  )
}
