import { ArrowDownRight, Clock3, Mail, MapPin, Send } from 'lucide-react'
import { FormEvent, useState } from 'react'
import { useSatriaStore } from '../store/useSatriaStore'
import { Panel } from '../components/Panel'
import { api } from '../services/api'

export function CommandView() {
  const view = useSatriaStore((state) => state.view)
  const filters = useSatriaStore((state) => state.filters)
  const emailConfigured = useSatriaStore((state) => Boolean(state.system?.email?.configured))
  const [emailOpen, setEmailOpen] = useState(false)
  const [email, setEmail] = useState('')
  const [emailState, setEmailState] = useState('')
  if (!view) return null
  const summary = view.summary
  const lowest = view.rankings.lowest_units.slice(0, 5)
  const sendBrief = async (event: FormEvent) => {
    event.preventDefault()
    setEmailState('Mengirim briefing…')
    try {
      const result: any = await api.emailReport(email, filters)
      setEmailState(result.message || 'Briefing terkirim.')
    } catch (error) {
      setEmailState(error instanceof Error ? error.message : 'Briefing tidak dapat dikirim.')
    }
  }
  return (
    <Panel
      title="Gambaran kesiapan nasional"
      description="Satu pembacaan dari seluruh observasi yang lolos filter aktif."
    >
      <div className="command-reading">
        <div className="hero-reading">
          <span>Indeks kesiapan</span>
          <strong>{summary.average_readiness === null ? '—' : summary.average_readiness.toFixed(1)}</strong>
          <small>rata-rata dari {summary.record_count.toLocaleString('id-ID')} rekaman</small>
        </div>
        <div className="reading-context">
          <p>
            {summary.attention_count.toLocaleString('id-ID')} observasi berada pada lensa perhatian karena indeks di bawah 80 atau berstatus ditandai.
          </p>
          <div><MapPin size={15} /> {summary.province_count} provinsi terwakili</div>
          <div><Clock3 size={15} /> Sinkronisasi terbaru {summary.latest_sync ? new Date(summary.latest_sync).toLocaleString('id-ID') : 'tidak tersedia'}</div>
        </div>
      </div>
      <div className="section-rule"><span>Unit dengan kesiapan terendah</span></div>
      <div className="rank-stack">
        {lowest.map((item, index) => (
          <div className="rank-line" key={`${item.unit}-${item.location}`}>
            <em>{String(index + 1).padStart(2, '0')}</em>
            <div><strong>{item.unit}</strong><span>{item.location} · {item.records} rekaman</span></div>
            <b>{item.readiness?.toFixed(1) ?? '—'}%</b>
            <ArrowDownRight size={16} />
          </div>
        ))}
      </div>
      <div className="brief-action">
        <button className="text-action" onClick={() => setEmailOpen((value) => !value)}><Mail size={14} /> Kirim ringkasan berbasis data aktif</button>
        {emailOpen && (emailConfigured ? (
          <form onSubmit={sendBrief}><input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="penerima@organisasi.id" aria-label="Email penerima briefing" /><button type="submit" aria-label="Kirim briefing"><Send size={14} /></button></form>
        ) : <span>Konfigurasikan SMTP di environment terlebih dahulu.</span>)}
        {emailState && <small>{emailState}</small>}
      </div>
    </Panel>
  )
}
