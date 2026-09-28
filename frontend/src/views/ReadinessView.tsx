import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Panel } from '../components/Panel'
import { useSatriaStore } from '../store/useSatriaStore'

export function ReadinessView() {
  const view = useSatriaStore((state) => state.view)
  if (!view) return null
  return (
    <Panel title="Distribusi kesiapan" description="Interval mempertahankan nilai sumber, termasuk observasi di luar rentang yang diharapkan." wide>
      <div className="split-analysis readiness-grid">
        <div className="chart-surface" aria-label="Grafik distribusi kesiapan">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={view.distributions.readiness} margin={{ left: -18, right: 8, top: 30, bottom: 2 }}>
              <CartesianGrid stroke="#80938b33" vertical={false} />
              <XAxis dataKey="name" tick={{ fill: '#41514b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#66756f', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: '#17666a12' }} contentStyle={{ background: '#f2f2eb', border: '1px solid #aab7b1', borderRadius: 12 }} />
              <Bar dataKey="count" name="Observasi" fill="#17666a" radius={[7, 7, 0, 0]}>
                <LabelList dataKey="count" position="top" fill="#31423c" fontSize={10} fontWeight={700} formatter={(value) => Number(value ?? 0).toLocaleString('id-ID')} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="province-bars">
          <h3>Kesiapan menurut provinsi</h3>
          {view.rankings.provinces.slice(0, 12).map((item) => {
            const value = item.readiness ?? 0
            return (
              <div key={item.location}>
                <span>{item.location}</span>
                <i><b style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></i>
                <strong>{item.readiness?.toFixed(1) ?? '—'}</strong>
              </div>
            )
          })}
        </div>
      </div>
    </Panel>
  )
}
