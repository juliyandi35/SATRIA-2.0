import { useSatriaStore } from '../store/useSatriaStore'

const number = new Intl.NumberFormat('id-ID')

export function MetricRibbon() {
  const loaded = useSatriaStore((state) => state.loaded)
  const summary = useSatriaStore((state) => state.view?.summary)
  if (!loaded || !summary) return null
  const metrics = [
    { label: 'Kesiapan nasional', value: summary.average_readiness === null ? '—' : `${summary.average_readiness.toFixed(1)}%` },
    { label: 'Rekaman aktif', value: number.format(summary.record_count) },
    { label: 'Unit', value: number.format(summary.unit_count) },
    { label: 'Provinsi', value: number.format(summary.province_count) },
    { label: 'Perlu perhatian', value: number.format(summary.attention_count), alert: summary.attention_count > 0 },
  ]
  return (
    <section className="metric-ribbon" aria-label="Ringkasan dataset aktif">
      {metrics.map((metric) => (
        <div key={metric.label}>
          <span>{metric.label}</span>
          <strong className={metric.alert ? 'alert-value' : ''}>{metric.value}</strong>
        </div>
      ))}
    </section>
  )
}
