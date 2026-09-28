import { Check, Database, KeyRound, LogOut, Mail, RefreshCw, Send, ShieldAlert, ShieldCheck, Trash2, Users, X } from 'lucide-react'
import { FormEvent, useState } from 'react'
import { AccountModal } from '../components/AccountModal'
import { Panel } from '../components/Panel'
import { SatriaSelect } from '../components/SatriaSelect'
import { api } from '../services/api'
import { useSatriaStore } from '../store/useSatriaStore'
import type { GraphicsPreset } from '../types'

export function SystemView({
  onNotice,
  onReset,
  onLogout,
  accountEmail,
  onEmailChanged,
}: {
  onNotice: (type: 'success' | 'error' | 'info', title: string, message: string) => void
  onReset: () => void
  onLogout: () => void
  accountEmail: string | null
  onEmailChanged: (email: string) => void
}) {
  const system = useSatriaStore((state) => state.system)
  const setSystem = useSatriaStore((state) => state.setSystem)
  const models = useSatriaStore((state) => state.models)
  const selectedModel = useSatriaStore((state) => state.selectedModel)
  const setSelectedModel = useSatriaStore((state) => state.setSelectedModel)
  const graphics = useSatriaStore((state) => state.graphicsPreset)
  const setGraphics = useSatriaStore((state) => state.setGraphicsPreset)
  const effective = useSatriaStore((state) => state.effectiveQuality)
  const fps = useSatriaStore((state) => state.fps)
  const rendererStats = useSatriaStore((state) => state.rendererStats)
  const localOnly = useSatriaStore((state) => state.localOnly)
  const setLocalOnly = useSatriaStore((state) => state.setLocalOnly)
  const audit = useSatriaStore((state) => state.auditLog)
  const setAudit = useSatriaStore((state) => state.setAuditLog)
  const emailConfigured = useSatriaStore((state) => Boolean(state.system?.email?.configured))
  const [confirmReset, setConfirmReset] = useState(false)
  const [confirmLogs, setConfirmLogs] = useState(false)
  const [logEmailOpen, setLogEmailOpen] = useState(false)
  const [logEmail, setLogEmail] = useState('')
  const [logEmailState, setLogEmailState] = useState('')
  const [accountModalOpen, setAccountModalOpen] = useState(false)

  const refresh = async () => {
    try { setSystem(await api.systemStatus()) }
    catch (error) { onNotice('error', 'Status gagal diperbarui', error instanceof Error ? error.message : 'Server tidak merespons.') }
  }
  const testDb = async () => {
    try { const result: any = await api.dbTest(); onNotice('success', 'Database terhubung', `${result.tables?.length ?? 0} tabel dapat dibaca.`) }
    catch (error) { onNotice('error', 'Database bermasalah', error instanceof Error ? error.message : 'Koneksi gagal.') }
  }
  const clearLogs = async () => {
    if (!confirmLogs) { setConfirmLogs(true); return }
    try { await api.clearLogs(); onNotice('success', 'Log dikosongkan', 'Berkas audit lokal telah dikosongkan.'); setConfirmLogs(false) }
    catch (error) { onNotice('error', 'Log tidak dapat dikosongkan', String(error)) }
  }
  const reset = () => {
    if (!confirmReset) { setConfirmReset(true); return }
    onReset(); setConfirmReset(false)
  }
  const sendLogEmail = async (event: FormEvent) => {
    event.preventDefault()
    setLogEmailState('Mengirim log…')
    try {
      const result: any = await api.emailAuditLog(logEmail)
      setLogEmailState(result.message || 'Log audit terkirim.')
    } catch (error) {
      setLogEmailState(error instanceof Error ? error.message : 'Log audit tidak dapat dikirim.')
    }
  }
  const services = [
    ['Backend Flask', system?.backend?.status],
    ['Dataset aktif', system?.dataset?.loaded ? 'online' : 'empty'],
    ['Ollama lokal', system?.ollama?.status],
    ['Checkpoint SQLite', system?.checkpoint_database?.status],
    ['MySQL opsional', system?.mysql?.status],
    ['Email', system?.email?.configured ? 'configured' : 'not_configured'],
  ]

  return (
    <Panel title="Kendali sistem" description="Semua indikator berasal dari pemeriksaan runtime, bukan status dekoratif." wide>
      <div className="system-grid">
        <section>
          <h3>Akun</h3>
          <div className="runtime-copy">
            <strong>{accountEmail || 'Tidak diketahui'}</strong>
            <span>Verifikasi dua langkah (MFA) aktif untuk akun ini.</span>
          </div>
          <button className="quiet-action full" onClick={onLogout}><LogOut size={15} /> Keluar dari sesi ini</button>
          <button className="quiet-action full" onClick={() => setAccountModalOpen(true)}><Users size={15} /> Kelola akun</button>
          <div className="security-note">
            <KeyRound size={18} />
            <span>
              <strong>Login dua faktor</strong>
              <small>Kata sandi dan kode authenticator diperiksa bersamaan pada setiap masuk.</small>
            </span>
            <ShieldCheck size={16} />
          </div>
        </section>
        <section>
          <div className="subheading"><h3>Kesehatan layanan</h3><button className="icon-button" onClick={refresh} aria-label="Perbarui status"><RefreshCw size={15} /></button></div>
          <div className="service-list">
            {services.map(([label, value]) => <div key={label}><i className={value === 'online' || value === 'configured' ? 'online' : value === 'empty' || value === 'not_configured' ? 'idle' : 'error'} /><span>{label}</span><b>{value || 'memeriksa'}</b></div>)}
          </div>
          {system?.backend?.python && <div className="runtime-copy"><strong>Python {system.backend.python.version}</strong><span>{system.backend.python.base_prefix}</span></div>}
          <button className="quiet-action full" onClick={testDb}><Database size={15} /> Uji database checkpoint</button>
        </section>
        <section>
          <h3>Model dan privasi</h3>
          <div className="control-label"><span>Model SATRIA AI</span><SatriaSelect value={selectedModel} onChange={setSelectedModel} ariaLabel="Model SATRIA AI" options={models.map((model) => ({ value: model.name, label: `${model.name}${model.available ? '' : ' — tidak tersedia'}`, disabled: !model.available }))} /></div>
          <label className="toggle-line"><span><strong>Eksekusi lokal</strong><small>Blokir pencarian dan pengiriman eksternal.</small></span><input type="checkbox" checked={localOnly} onChange={(event) => setLocalOnly(event.target.checked)} /><i /></label>
          <label className="toggle-line"><span><strong>Audit percakapan</strong><small>Catat kueri dan respons pada log lokal.</small></span><input type="checkbox" checked={audit} onChange={(event) => setAudit(event.target.checked)} /><i /></label>
        </section>
        <section>
          <h3>Mesin visual</h3>
          <div className="control-label"><span>Preset grafis</span><SatriaSelect value={graphics} onChange={(value) => setGraphics(value as GraphicsPreset)} ariaLabel="Preset grafis" options={['AUTO', 'LOW', 'MEDIUM', 'HIGH', 'ULTRA'].map((preset) => ({ value: preset, label: preset }))} /></div>
          <div className="renderer-reading"><span>Preset efektif</span><strong>{effective}</strong><span>Frame rate</span><strong>{fps || '—'} FPS</strong><span>Draw calls</span><strong>{rendererStats.drawCalls}</strong><span>Segitiga</span><strong>{rendererStats.triangles.toLocaleString('id-ID')}</strong><span>Geometri / tekstur</span><strong>{rendererStats.geometries} / {rendererStats.textures}</strong>{rendererStats.heapMb !== null && <><span>Heap JavaScript</span><strong>{rendererStats.heapMb} MB</strong></>}</div>
          <p className="micro-copy">AUTO memakai frame time berkelanjutan, hysteresis, dan cooldown delapan detik sebelum berpindah kualitas.</p>
        </section>
        <section>
          <h3>Kontrol data</h3>
          <div className="danger-actions">
            <button onClick={clearLogs}><Trash2 size={15} /> {confirmLogs ? 'Klik lagi untuk kosongkan log' : 'Kosongkan log audit'}</button>
            <button onClick={reset}><Trash2 size={15} /> {confirmReset ? 'Klik lagi untuk lepas dataset' : 'Lepas dataset aktif'}</button>
          </div>
          <div className="brief-action">
            <button className="text-action" onClick={() => setLogEmailOpen((value) => !value)}><Mail size={14} /> Kirimkan audit log via email</button>
            {logEmailOpen && (emailConfigured ? (
              <form onSubmit={sendLogEmail}><input type="email" required value={logEmail} onChange={(event) => setLogEmail(event.target.value)} placeholder="penerima@organisasi.id" aria-label="Email penerima audit log" /><button type="submit" aria-label="Kirim audit log"><Send size={14} /></button></form>
            ) : <span>Konfigurasikan SMTP di environment terlebih dahulu.</span>)}
            {logEmailState && <small>{logEmailState}</small>}
          </div>
          <div className={localOnly ? 'security-note' : 'security-note warning'}>
            {localOnly ? <ShieldCheck size={18} /> : <ShieldAlert size={18} />}
            <span>
              <strong>{localOnly ? 'Perimeter lokal aktif' : 'Perimeter lokal nonaktif'}</strong>
              <small>
                {localOnly
                  ? 'Tool eksternal (pencarian web, laporan via email) diblokir. '
                  : 'Tool eksternal (pencarian web, laporan via email) diizinkan. '}
                Path alat AI tetap dibatasi pada direktori proyek dan SQL tetap SELECT-only.
              </small>
            </span>
            {localOnly ? <Check size={16} /> : <X size={16} />}
          </div>
        </section>
      </div>
      <AccountModal
        open={accountModalOpen}
        onClose={() => setAccountModalOpen(false)}
        accountEmail={accountEmail}
        onEmailChanged={onEmailChanged}
        onLogout={onLogout}
        onNotice={onNotice}
      />
    </Panel>
  )
}
