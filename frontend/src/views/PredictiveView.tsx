import { RefreshCw } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Panel } from '../components/Panel'
import { useSatriaStore } from '../store/useSatriaStore'

export function PredictiveView({ loading, onRefresh }: { loading: boolean; onRefresh: () => void }) {
  const result = useSatriaStore((state) => state.predictive)
  return (
    <Panel title="Risiko tersembunyi" description="Isolation Forest mendeteksi struktur yang tidak lazim; ini bukan ramalan deret waktu." wide>
      <div className="analysis-toolbar">
        <div>{result && <><strong>{result.anomaly_count}</strong><span>anomali model · pemisahan {result.confidence.toFixed(1)}%</span></>}</div>
        <button className="quiet-action compact" onClick={onRefresh} disabled={loading}><RefreshCw size={15} className={loading ? 'spin' : ''} /> Jalankan analisis</button>
      </div>
      {!result ? <div className="soft-empty">Menjalankan Isolation Forest pada dataset aktif…</div> : (
        <div className="split-analysis predictive-grid">
          <div className="chart-surface">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={result.top_risks.slice(0, 10)} layout="vertical" margin={{ left: 18, right: 18 }}>
                <CartesianGrid stroke="#80938b33" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} hide />
                <YAxis type="category" dataKey="unit" width={105} tick={{ fill: '#41514b', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: '#f2f2eb', border: '1px solid #aab7b1', borderRadius: 12 }} />
                <Bar dataKey="hidden_risk" name="Risiko tersembunyi" fill="#9b3d36" radius={[0, 7, 7, 0]}>
                  <LabelList dataKey="hidden_risk" position="insideRight" fill="#f7f1e8" fontSize={9} fontWeight={700} formatter={(value) => Number(value ?? 0).toFixed(1)} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="risk-ledger">
            {result.top_risks.slice(0, 8).map((risk, index) => (
              <div key={risk.id}>
                <em>{String(index + 1).padStart(2, '0')}</em>
                <span><strong>{risk.unit}</strong><small>{risk.location} · {risk.category}</small></span>
                <b>{risk.hidden_risk.toFixed(1)}</b>
              </div>
            ))}
          </div>
        </div>
      )}
    </Panel>
  )
}
