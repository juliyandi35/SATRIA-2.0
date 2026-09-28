import { Lock, Pencil, ShieldCheck, Trash2, UserPlus, X } from 'lucide-react'
import QRCode from 'qrcode'
import { FormEvent, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../services/api'

type Account = { email: string; mfa_enabled: boolean; created_at: string }
type Notify = (type: 'success' | 'error' | 'info', title: string, message: string) => void

export function AccountModal({
  open,
  onClose,
  accountEmail,
  onEmailChanged,
  onLogout,
  onNotice,
}: {
  open: boolean
  onClose: () => void
  accountEmail: string | null
  onEmailChanged: (email: string) => void
  onLogout: () => void
  onNotice: Notify
}) {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [pwState, setPwState] = useState('')
  const [emailPassword, setEmailPassword] = useState('')
  const [newEmail, setNewEmail] = useState('')
  const [emailState, setEmailState] = useState('')
  const [accounts, setAccounts] = useState<Account[]>([])
  const [addOpen, setAddOpen] = useState(false)
  const [addPassword, setAddPassword] = useState('')
  const [addEmail, setAddEmail] = useState('')
  const [addNewPassword, setAddNewPassword] = useState('')
  const [addState, setAddState] = useState('')
  const [addResult, setAddResult] = useState<{ email: string; totp_secret: string; provisioning_uri: string } | null>(null)
  const [addQr, setAddQr] = useState('')
  const [addVerifyCode, setAddVerifyCode] = useState('')
  const [addVerifyState, setAddVerifyState] = useState('')
  const [removeTarget, setRemoveTarget] = useState<string | null>(null)
  const [removePassword, setRemovePassword] = useState('')
  const [removeState, setRemoveState] = useState('')

  const loadAccounts = () => {
    api.auth.accounts().then((result) => setAccounts(result.accounts))
      .catch((error) => onNotice('error', 'Gagal memuat akun', error instanceof Error ? error.message : 'Server tidak merespons.'))
  }

  useEffect(() => { if (open) loadAccounts() }, [open])

  useEffect(() => {
    if (!addResult) { setAddQr(''); return }
    let active = true
    QRCode.toString(addResult.provisioning_uri, { type: 'svg', margin: 1, width: 152 })
      .then((svg) => { if (active) setAddQr(svg) })
      .catch(() => { if (active) setAddQr('') })
    return () => { active = false }
  }, [addResult])

  if (!open) return null

  const submitPasswordChange = async (event: FormEvent) => {
    event.preventDefault()
    setPwState('')
    if (newPassword !== confirmPassword) { setPwState('Konfirmasi kata sandi baru tidak cocok.'); return }
    try {
      await api.auth.changePassword(currentPassword, newPassword)
      setPwState('Kata sandi berhasil diganti.')
      setCurrentPassword(''); setNewPassword(''); setConfirmPassword('')
      onNotice('success', 'Kata sandi diperbarui', 'Gunakan kata sandi baru pada sesi masuk berikutnya.')
    } catch (error) {
      setPwState(error instanceof Error ? error.message : 'Kata sandi tidak dapat diganti.')
    }
  }

  const submitEmailChange = async (event: FormEvent) => {
    event.preventDefault()
    setEmailState('')
    try {
      const result = await api.auth.changeEmail(emailPassword, newEmail)
      setEmailState('E-mail akun berhasil diganti.')
      setEmailPassword(''); setNewEmail('')
      onEmailChanged(result.email)
      onNotice('success', 'E-mail akun diperbarui', `Akun sekarang terdaftar sebagai ${result.email}.`)
      loadAccounts()
    } catch (error) {
      setEmailState(error instanceof Error ? error.message : 'E-mail tidak dapat diganti.')
    }
  }

  const submitAddAccount = async (event: FormEvent) => {
    event.preventDefault()
    setAddState('')
    try {
      const result = await api.auth.addAccount(addPassword, addEmail, addNewPassword)
      setAddResult(result)
      setAddPassword(''); setAddEmail(''); setAddNewPassword('')
      onNotice('success', 'Akun ditambahkan', `${result.email} dapat menyelesaikan pendaftaran MFA sendiri lewat layar masuk.`)
      loadAccounts()
    } catch (error) {
      setAddState(error instanceof Error ? error.message : 'Akun tidak dapat ditambahkan.')
    }
  }

  const submitVerifyAdd = async (event: FormEvent) => {
    event.preventDefault()
    setAddVerifyState('')
    if (!addResult) return
    try {
      await api.auth.enrollMfa(addResult.email, addVerifyCode)
      onNotice('success', 'MFA aktif', `${addResult.email} kini dapat masuk dengan kata sandi dan verifikator.`)
      setAddResult(null); setAddVerifyCode(''); setAddQr('')
      loadAccounts()
    } catch (error) {
      setAddVerifyState(error instanceof Error ? error.message : 'Kode verifikasi salah.')
    }
  }

  const submitRemoveAccount = async (event: FormEvent, targetEmail: string) => {
    event.preventDefault()
    setRemoveState('')
    try {
      const result = await api.auth.removeAccount(removePassword, targetEmail)
      setRemoveTarget(null); setRemovePassword('')
      onNotice('success', 'Akun dihapus', `${targetEmail} telah dihapus dari sistem.`)
      if (result.removed_self) { onLogout(); return }
      loadAccounts()
    } catch (error) {
      setRemoveState(error instanceof Error ? error.message : 'Akun tidak dapat dihapus.')
    }
  }

  return createPortal(
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="account-modal-title" onClick={onClose}>
      <div className="modal-card" onClick={(event) => event.stopPropagation()}>
        <header>
          <div>
            <p className="scene-kicker">Kendali sistem</p>
            <h2 id="account-modal-title">Kelola akun</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Tutup"><X size={16} /></button>
        </header>
        <div className="modal-body">
          <p className="micro-copy">Masuk sebagai <strong>{accountEmail || 'Tidak diketahui'}</strong>. Setiap perubahan wajib konfirmasi kata sandi Anda saat ini.</p>

          <div className="account-list">
            {accounts.map((account) => (
              <div key={account.email} className="account-row">
                <span>
                  <strong>{account.email}</strong>
                  <small>{account.mfa_enabled ? 'MFA aktif' : 'Menunggu pendaftaran MFA'}{account.email === accountEmail ? ' - akun ini' : ''}</small>
                </span>
                {removeTarget === account.email ? (
                  <form className="account-row-confirm" onSubmit={(event) => submitRemoveAccount(event, account.email)}>
                    <input type="password" required placeholder="Kata sandi Anda" value={removePassword} onChange={(event) => setRemovePassword(event.target.value)} />
                    <button type="submit" className="icon-button" aria-label={`Konfirmasi hapus ${account.email}`}><Trash2 size={14} /></button>
                    <button type="button" className="icon-button" onClick={() => { setRemoveTarget(null); setRemovePassword(''); setRemoveState('') }} aria-label="Batal"><X size={14} /></button>
                  </form>
                ) : (
                  <button className="icon-button" onClick={() => setRemoveTarget(account.email)} aria-label={`Hapus ${account.email}`}><Trash2 size={14} /></button>
                )}
              </div>
            ))}
            {removeState && <small className="modal-inline-state">{removeState}</small>}
          </div>

          <div className="account-action">
            <button className="text-action" onClick={() => setAddOpen((value) => !value)}><UserPlus size={14} /> Buat akun baru</button>
            {addOpen && (
              <form onSubmit={submitAddAccount} className="auth-field-stack">
                <label className="auth-field">Kata sandi Anda saat ini<input type="password" required value={addPassword} onChange={(event) => setAddPassword(event.target.value)} /></label>
                <label className="auth-field">E-mail akun baru<input type="email" required value={addEmail} onChange={(event) => setAddEmail(event.target.value)} placeholder="rekan@organisasi.id" /></label>
                <label className="auth-field">Kata sandi awal akun baru<input type="password" required minLength={10} value={addNewPassword} onChange={(event) => setAddNewPassword(event.target.value)} /></label>
                <button className="quiet-action full" type="submit"><UserPlus size={14} /> Tambah akun</button>
              </form>
            )}
            {addState && <small className="modal-inline-state">{addState}</small>}
            {addResult && (
              <>
                <p className="micro-copy">
                  Minta {addResult.email} memindai kode ini dengan aplikasi authenticator, lalu masukkan kode 6 digit
                  yang muncul di sini untuk langsung mengaktifkan MFA. Bisa juga dilewati dan diselesaikan sendiri
                  nanti di layar masuk.
                </p>
                {addQr && <div className="auth-qr" dangerouslySetInnerHTML={{ __html: addQr }} />}
                <div className="auth-secret">{addResult.totp_secret.match(/.{1,4}/g)?.join(' ')}</div>
                <form onSubmit={submitVerifyAdd} className="auth-field-stack">
                  <label className="auth-field">
                    Kode verifikator
                    <input
                      type="text"
                      inputMode="numeric"
                      pattern="[0-9]{6}"
                      required
                      maxLength={6}
                      value={addVerifyCode}
                      onChange={(event) => setAddVerifyCode(event.target.value)}
                      placeholder="123456"
                    />
                  </label>
                  <button className="quiet-action full" type="submit"><ShieldCheck size={14} /> Verifikasi &amp; aktifkan MFA</button>
                </form>
                {addVerifyState && <small className="modal-inline-state">{addVerifyState}</small>}
              </>
            )}
          </div>

          <div className="modal-grid">
            <div className="account-action">
              <p className="subheading-label"><Lock size={13} /> Ganti kata sandi</p>
              <form onSubmit={submitPasswordChange} className="auth-field-stack">
                <label className="auth-field">Kata sandi saat ini<input type="password" required value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></label>
                <label className="auth-field">Kata sandi baru<input type="password" required minLength={10} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></label>
                <label className="auth-field">Konfirmasi kata sandi baru<input type="password" required minLength={10} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} /></label>
                <button className="quiet-action full" type="submit"><Lock size={14} /> Simpan kata sandi baru</button>
              </form>
              {pwState && <small className="modal-inline-state">{pwState}</small>}
            </div>
            <div className="account-action">
              <p className="subheading-label"><Pencil size={13} /> Ganti e-mail akun ini</p>
              <form onSubmit={submitEmailChange} className="auth-field-stack">
                <label className="auth-field">Kata sandi saat ini<input type="password" required value={emailPassword} onChange={(event) => setEmailPassword(event.target.value)} /></label>
                <label className="auth-field">E-mail baru<input type="email" required value={newEmail} onChange={(event) => setNewEmail(event.target.value)} placeholder="nama.baru@organisasi.id" /></label>
                <button className="quiet-action full" type="submit"><Pencil size={14} /> Simpan e-mail baru</button>
              </form>
              {emailState && <small className="modal-inline-state">{emailState}</small>}
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
