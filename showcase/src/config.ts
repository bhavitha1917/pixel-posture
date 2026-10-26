/**
 * Site configuration. The repository URL is the single configuration point for every
 * GitHub/README link; set VITE_REPO_URL (see .env.example). Until then links render as
 * "coming soon" instead of pointing somewhere that does not exist.
 */
export function parseRepoUrl(value: string | undefined): string | null {
  const url = value?.trim()
  if (!url) return null
  return /^https:\/\/\S+$/.test(url) ? url.replace(/\/+$/, '') : null
}

export const REPO_URL = parseRepoUrl(import.meta.env.VITE_REPO_URL)
export const README_URL = REPO_URL ? `${REPO_URL}#readme` : null
