import {
  Activity,
  Bot,
  Boxes,
  Database,
  Gauge,
  Map,
  Orbit,
  ScanSearch,
  Settings2,
} from 'lucide-react'
import { useSatriaStore } from '../store/useSatriaStore'
import type { Zone } from '../types'

const zones: Array<{ id: Zone; label: string; icon: typeof Orbit }> = [
  { id: 'command', label: 'Nexus', icon: Orbit },
  { id: 'map', label: 'Nusantara', icon: Map },
  { id: 'readiness', label: 'Kesiapan', icon: Gauge },
  { id: 'spatial', label: 'Risiko spasial', icon: Boxes },
  { id: 'predictive', label: 'Risiko tersembunyi', icon: ScanSearch },
  { id: 'diagnostics', label: 'Diagnostik', icon: Activity },
  { id: 'data', label: 'Data', icon: Database },
  { id: 'ai', label: 'SATRIA AI', icon: Bot },
  { id: 'system', label: 'Sistem', icon: Settings2 },
]

export function CommandRail() {
  const active = useSatriaStore((state) => state.zone)
  const setZone = useSatriaStore((state) => state.setZone)
  return (
    <aside className="command-rail" aria-label="Zona intelijen">
      <button className="brand-mark" onClick={() => setZone('command')} aria-label="Buka Command Nexus">
        <span>S</span>
        <i />
      </button>
      <nav>
        {zones.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={active === id ? 'rail-button active' : 'rail-button'}
            onClick={() => setZone(id)}
            aria-label={label}
            aria-current={active === id ? 'page' : undefined}
            title={label}
          >
            <Icon size={18} strokeWidth={1.65} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="rail-signature">2.0</div>
    </aside>
  )
}
