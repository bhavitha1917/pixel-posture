import { Check, Copy } from 'lucide-react'
import { useEffect, useState } from 'react'

const RESET_MS = 1800

export function CodeBlock({ code, label }: { code: string; label: string }) {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle')

  useEffect(() => {
    if (state === 'idle') return
    const id = window.setTimeout(() => setState('idle'), RESET_MS)
    return () => window.clearTimeout(id)
  }, [state])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setState('copied')
    } catch {
      setState('failed')
    }
  }

  return (
    <div className="codeblock">
      <pre aria-label={label}>
        <code>{code}</code>
      </pre>
      <button type="button" onClick={copy} aria-label={`Copy ${label}`}>
        {state === 'copied' ? <Check size={14} aria-hidden /> : <Copy size={14} aria-hidden />}
        {state === 'copied' ? 'Copied' : state === 'failed' ? 'Select & copy' : 'Copy'}
      </button>
      <span className="visually-hidden" aria-live="polite">
        {state === 'copied' ? 'Copied to clipboard' : ''}
      </span>
    </div>
  )
}
