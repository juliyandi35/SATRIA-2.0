import { RefreshCw, ScanLine } from 'lucide-react'
import { useState } from 'react'
import { Panel } from '../components/Panel'
import { useSatriaStore } from '../store/useSatriaStore'
import type { Cluster, SpatialVisualMode } from '../types'

const visualModes: Array<{ value: SpatialVisualMode; label: string }> = [
  { value: 'points', label: 'Titik risiko' },
  { value: 'clusters', label: 'Amplop klaster' },
  { value: 'combined', label: 'Gabungan' },
]

type ClusterSort = 'id' | 'readiness'
const sortModes: Array<{ value: ClusterSort; label: string }> = [
  { value: 'id', label: 'ID' },
  { value: 'readiness', label: 'Kesiapan' },
]

function sortClusters(clusters: Cluster[], sort: ClusterSort): Cluster[] {
  if (sort === 'id') return [...clusters].sort((a, b) => Number(a.cluster_id.slice(2)) - Number(b.cluster_id.slice(2)))
  return [...clusters].sort((a, b) => (a.average_readiness ?? Infinity) - (b.average_readiness ?? Infinity))
}

export function SpatialView({ loading, onRefresh }: { loading: boolean; onRefresh: () => void }) {
  const result = useSatriaStore((state) => state.spatial)
  const visualMode = useSatriaStore((state) => state.spatialVisualMode)
  const setVisualMode = useSatriaStore((state) => state.setSpatialVisualMode)
  const [clusterSort, setClusterSort] = useState<ClusterSort>('id')
  const severityLabel = { CRITICAL: 'KRITIS', HIGH: 'TINGGI', WATCH: 'PANTAU' }
  return (
    <Panel title="Medan risiko spasial" description="Zona dihitung dengan Haversine DBSCAN; amplop 3D mengikuti koordinat anggota klaster." wide>
      <div className="analysis-toolbar">
        <div><ScanLine size={17} /><span>{result ? `${result.risk_point_count} titik risiko` : 'Analisis belum dijalankan'}</span></div>
        <button className="quiet-action compact" onClick={onRefresh} disabled={loading}><RefreshCw size={15} className={loading ? 'spin' : ''} /> Hitung ulang</button>
      </div>
      <div className="spatial-mode-group">
        <div className="spatial-mode-row">
          <span>Visual peta</span>
          <div className="segmented-control" role="group" aria-label="Mode visual risiko spasial">
            {visualModes.map((mode) => <button key={mode.value} type="button" aria-pressed={visualMode === mode.value} className={visualMode === mode.value ? 'active' : ''} onClick={() => setVisualMode(mode.value)}>{mode.label}</button>)}
          </div>
        </div>
        {result && result.clusters.length > 0 && (
          <div className="spatial-mode-row">
            <span>Urutkan</span>
            <div className="segmented-control" role="group" aria-label="Urutkan klaster">
              {sortModes.map((mode) => <button key={mode.value} type="button" aria-pressed={clusterSort === mode.value} className={clusterSort === mode.value ? 'active' : ''} onClick={() => setClusterSort(mode.value)}>{mode.label}</button>)}
            </div>
          </div>
        )}
      </div>
      {!result ? <div className="soft-empty">Mempersiapkan klaster dari data aktif…</div> : result.clusters.length === 0 ? (
        <div className="soft-empty">Tidak ada klaster yang memenuhi parameter saat ini. {result.noise_count} titik tercatat sebagai noise.</div>
      ) : (
        <div className="cluster-list">
          {sortClusters(result.clusters, clusterSort).map((cluster) => (
            <article key={cluster.cluster_id}>
              <div className={`severity ${cluster.severity.toLowerCase()}`}>{severityLabel[cluster.severity]}</div>
              <div><strong>{cluster.cluster_id}</strong><span>{cluster.locations.slice(0, 3).join(', ')}</span></div>
              <dl><div><dt>Anggota</dt><dd>{cluster.member_count}</dd></div><div><dt>Unit</dt><dd>{cluster.unit_count}</dd></div><div><dt>Kesiapan</dt><dd>{cluster.average_readiness === null ? '—' : `${cluster.average_readiness.toFixed(1)}%`}</dd></div></dl>
            </article>
          ))}
        </div>
      )}
    </Panel>
  )
}
