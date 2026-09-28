import { ArrowRight, Database, Radio, ShieldCheck } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

export function WelcomeGate({
  loaded,
  model,
  onEnter,
}: {
  loaded: boolean
  model: string
  onEnter: () => void
}) {
  const [leaving, setLeaving] = useState(false)

  const enter = useCallback(() => {
    if (leaving) return
    setLeaving(true)
    window.setTimeout(onEnter, 520)
  }, [leaving, onEnter])

  useEffect(() => {
    const handleKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Enter') enter()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [enter])

  return (
    <section className={`welcome-gate ${leaving ? 'leaving' : ''}`} aria-labelledby="welcome-title">
      <div className="welcome-scan" aria-hidden="true"><i /><i /><i /></div>
      <div className="welcome-emblem" aria-hidden="true">
        <div className="welcome-orbit orbit-one" />
        <div className="welcome-orbit orbit-two" />
        <div className="welcome-orbit orbit-three" />
        <span>S</span>
        <b />
      </div>
      <div className="welcome-copy">
        <p className="welcome-salutation">Greetings, Commander</p>
        <h1 id="welcome-title">Welcome to SATRIA<br />Command Center</h1>
        <p className="welcome-description">Satu ruang komando untuk membaca kesiapan, medan risiko, dan sinyal tersembunyi Nusantara.</p>
        <button className="welcome-enter" type="button" onClick={enter}>
          Enter Command Center <ArrowRight size={18} />
        </button>
        <span className="welcome-key-hint">Tekan Enter untuk masuk</span>
        <div className="welcome-status" aria-label="Status awal sistem">
          <span><Radio size={14} /><b>Sistem lokal</b> online</span>
          <span><Database size={14} /><b>Dataset</b> {loaded ? 'siap' : 'menunggu'}</span>
          <span><ShieldCheck size={14} /><b>Model</b> {model}</span>
        </div>
      </div>
    </section>
  )
}
