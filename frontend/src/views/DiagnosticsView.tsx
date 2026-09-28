import { RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { Panel } from '../components/Panel'
import { useSatriaStore } from '../store/useSatriaStore'

export function DiagnosticsView({ loading, onRefresh }: { loading: boolean; onRefresh: () => void }) {
  const result = useSatriaStore((state) => state.diagnostics)
  const [detail, setDetail] = useState<string>('outliers')
  const ids: string[] = result?.details_ids?.[detail] || []
  return (
    <Panel title="Integritas dataset" description="Masalah sumber tetap terlihat dan tidak ditambal atau dibuang secara diam-diam." wide>
      <div className="analysis-toolbar">
        <div>{result && <><strong>{result.quality.score.toFixed(2)}</strong><span>skor kualitas transparan</span></>}</div>
        <button className="quiet-action compact" onClick={onRefresh} disabled={loading}><RefreshCw size={15} className={loading ? 'spin' : ''} /> Periksa ulang</button>
      </div>
      {!result ? <div className="soft-empty">Memeriksa skema, nilai hilang, duplikasi, rentang, dan koordinat…</div> : (
        <>
          <div className="diagnostic-strip">
            <button onClick={() => setDetail('missing')}><span>Nilai hilang</span><strong>{result.details_ids.missing.length}</strong></button>
            <button onClick={() => setDetail('duplicates')}><span>Duplikasi</span><strong>{result.details_ids.duplicates.length}</strong></button>
            <button onClick={() => setDetail('outliers')}><span>Outlier IQR</span><strong>{result.details_ids.outliers.length}</strong></button>
            <button onClick={() => setDetail('out_of_range')}><span>Di luar 0–100</span><strong>{result.details_ids.out_of_range.length}</strong></button>
            <button onClick={() => setDetail('invalid_coordinates')}><span>Koordinat invalid</span><strong>{result.details_ids.invalid_coordinates.length}</strong></button>
          </div>
          <div className="diagnostic-body">
            <div>
              <h3>Skema normalisasi</h3>
              {Object.entries(result.schema).map(([name, type]) => <div className="schema-line" key={name}><span>{name}</span><b>{String(type)}</b></div>)}
            </div>
            <div>
              <h3>ID terdampak · {detail.replaceAll('_', ' ')}</h3>
              {ids.length ? <div className="id-cloud">{ids.slice(0, 120).map((id) => <span key={id}>{id}</span>)}</div> : <div className="soft-empty compact-empty">Tidak ada rekaman pada kategori ini.</div>}
            </div>
          </div>
        </>
      )}
    </Panel>
  )
}
