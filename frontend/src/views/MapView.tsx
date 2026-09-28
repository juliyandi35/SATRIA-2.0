import { LocateFixed, MousePointer2 } from 'lucide-react'
import { Panel } from '../components/Panel'
import { useSatriaStore } from '../store/useSatriaStore'

export function MapView() {
  const view = useSatriaStore((state) => state.view)
  if (!view) return null
  return (
    <Panel title="Peta operasional Nusantara" description="Node geografis di dunia 3D berasal dari unit dan koordinat dataset aktif.">
      <div className="map-instructions">
        <LocateFixed size={28} />
        <h3>{view.map_points.length.toLocaleString('id-ID')} node geografis</h3>
        <p>Tarik panggung peta untuk memutar atau mengubah tilt, scroll atau pinch untuk zoom mendekati titik yang berdempetan. Gerakkan penunjuk ke beacon untuk melihat unit, lokasi, dan indeks kesiapan.</p>
        <div className="legend-row"><i className="jade" /> Siap <i className="bronze" /> Perhatian <i className="oxide" /> Ditandai / rendah</div>
        <span className="interaction-hint"><MousePointer2 size={14} /> Drag untuk menjelajah · scroll untuk zoom · klik keterangan lalu "Inspeksi" (10 detik) untuk membuka detail batalyon.</span>
      </div>
      <div className="section-rule"><span>Cakupan provinsi</span></div>
      <div className="province-mini-list">
        {view.rankings.provinces.slice(0, 10).map((province) => (
          <div key={province.location}>
            <span>{province.location}</span><b>{province.readiness?.toFixed(1) ?? '—'}%</b>
          </div>
        ))}
      </div>
    </Panel>
  )
}
