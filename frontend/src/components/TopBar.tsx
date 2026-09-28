import { Expand, Minimize2, Radio } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSatriaStore } from '../store/useSatriaStore'
import type { Zone } from '../types'

const zoneTitles: Record<Zone, string> = {
  command: 'Command Nexus',
  map: 'Peta Nusantara',
  readiness: 'Intelijen kesiapan',
  spatial: 'Risiko spasial',
  predictive: 'Risiko tersembunyi',
  diagnostics: 'Diagnostik data',
  data: 'Akses data',
  ai: 'SATRIA AI',
  system: 'Kendali sistem',
}

export function TopBar() {
  const zone = useSatriaStore((state) => state.zone)
  const loaded = useSatriaStore((state) => state.loaded)
  const selectedModel = useSatriaStore((state) => state.selectedModel)
  const [now, setNow] = useState(new Date())
  const [fullscreen, setFullscreen] = useState(Boolean(document.fullscreenElement))

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 30_000)
    const change = () => setFullscreen(Boolean(document.fullscreenElement))
    document.addEventListener('fullscreenchange', change)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('fullscreenchange', change)
    }
  }, [])

  const toggleFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen()
    else document.documentElement.requestFullscreen()
  }

  return (
    <header className="top-bar">
      <div className="zone-identity">
        <span className="live-mark"><i /> SATRIA 2.0</span>
        <h1>{zoneTitles[zone]}</h1>
      </div>
      <div className="system-line">
        <span className={loaded ? 'data-status ready' : 'data-status'}>
          <Radio size={14} /> {loaded ? 'Dataset aktif' : 'Menunggu data'}
        </span>
        <span className="model-name">{selectedModel}</span>
        <time dateTime={now.toISOString()}>
          {new Intl.DateTimeFormat('id-ID', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(now)} WIB
        </time>
        <button className="icon-button" onClick={toggleFullscreen} aria-label={fullscreen ? 'Keluar layar penuh' : 'Layar penuh'}>
          {fullscreen ? <Minimize2 size={17} /> : <Expand size={17} />}
        </button>
      </div>
    </header>
  )
}
