import type { ReactNode } from 'react'
import { README_URL, REPO_URL } from '../config'

interface Props {
  kind?: 'repo' | 'readme'
  children: ReactNode
  className?: string
}

/** Links to the GitHub repository, or an honest "coming soon" when it is not configured. */
export function RepoLink({ kind = 'repo', children, className }: Props) {
  const href = kind === 'readme' ? README_URL : REPO_URL
  if (!href) {
    return (
      <span className={`pending-link ${className ?? ''}`.trim()} title="Set VITE_REPO_URL to enable">
        {kind === 'readme' ? 'Full README: link coming soon' : 'Repository link coming soon'}
      </span>
    )
  }
  return (
    <a className={className} href={href} target="_blank" rel="noreferrer noopener">
      {children}
    </a>
  )
}
