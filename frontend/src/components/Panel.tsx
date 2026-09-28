import { Maximize2, Minus } from 'lucide-react'
import { useState } from 'react'
import type { ReactNode } from 'react'

export function Panel({ title, description, children, wide = false }: { title: string; description: string; children: ReactNode; wide?: boolean }) {
  const [minimized, setMinimized] = useState(false)
  return (
    <section className={`context-panel ${wide ? 'wide' : ''} ${minimized ? 'minimized' : ''}`.trim()}>
      <header>
        <div className="panel-heading"><h2>{title}</h2><p>{description}</p></div>
        <button
          className="panel-visibility"
          type="button"
          onClick={() => setMinimized((value) => !value)}
          aria-label={minimized ? `Buka panel ${title}` : `Minimalkan panel ${title}`}
          aria-expanded={!minimized}
          title={minimized ? 'Buka panel' : 'Minimalkan panel'}
        >
          {minimized ? <Maximize2 size={16} /> : <Minus size={18} />}
        </button>
      </header>
      {!minimized && <div className="panel-content">{children}</div>}
    </section>
  )
}
