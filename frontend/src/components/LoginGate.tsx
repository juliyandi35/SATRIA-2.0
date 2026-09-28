import { KeyRound, LoaderCircle, LogIn, ShieldCheck, UserPlus } from 'lucide-react'
import QRCode from 'qrcode'
import { FormEvent, useEffect, useState } from 'react'
import { api } from '../services/api'

type Mode = 'loading' | 'setup' | 'enroll' | 'login'

// Matches services/auth_service.py's authenticate() message for an account whose MFA was
// never enrolled (e.g. added via "Tambah akun"). The login screen is the only place such an
// account is ever shown, so on this specific rejection retry as enrollment instead of failing.
const MFA_NOT_ENROLLED = 'Penyiapan MFA belum selesai. Selesaikan pendaftaran verifikator terlebih dahulu.'

export function LoginGate({ onAuthenticated }: { onAuthenticated: (email: string) => void }) {
  const [mode, setMode] = useState<Mode>('loading')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [remember, setRemember] = useState(false)
  const [secret, setSecret] = useState('')
  const [provisioningUri, setProvisioningUri] = useState('')
  const [qrSvg, setQrSvg] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (mode !== 'enroll' || !provisioningUri) return
    let active = true
    QRCode.toString(provisioningUri, { type: 'svg', margin: 1, width: 176 })
      .then((svg) => { if (active) setQrSvg(svg) })
      .catch(() => { if (active) setQrSvg('') })
    return () => { active = false }
  }, [mode, provisioningUri])

  useEffect(() => {
    api.auth
      .status()
      .then((status) => setMode(status.configured ? 'login' : 'setup'))
      .catch(() => setError('Backend SATRIA belum dapat dijangkau.'))
  }, [])

  const submitSetup = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    if (password !== confirmPassword) {
      setError('Konfirmasi kata sandi tidak cocok.')
      return
    }
    setBusy(true)
    try {
      const result = await api.auth.setup(email, password)
      setSecret(result.totp_secret)
      setProvisioningUri(result.provisioning_uri)
      setMode('enroll')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Penyiapan akun gagal.')
    } finally {
      setBusy(false)
    }
  }

  const submitEnroll = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const result = await api.auth.enrollMfa(email, totpCode)
      onAuthenticated(result.email)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Kode verifikasi salah.')
    } finally {
      setBusy(false)
    }
  }

  const submitLogin = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const result = await api.auth.login(email, password, totpCode, remember)
      onAuthenticated(result.email)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Masuk gagal.'
      if (message === MFA_NOT_ENROLLED) {
        try {
          const enrolled = await api.auth.enrollMfa(email, totpCode, remember)
          onAuthenticated(enrolled.email)
          return
        } catch (enrollErr) {
          setError(enrollErr instanceof Error ? enrollErr.message : 'Kode verifikasi salah.')
          return
        }
      }
      setError(message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="auth-gate" aria-labelledby="auth-title">
      <div className="auth-card">
        <div className="import-emblem">
          {mode === 'loading' ? (
            <LoaderCircle className="spin" size={30} />
          ) : mode === 'enroll' ? (
            <ShieldCheck size={30} />
          ) : mode === 'setup' ? (
            <UserPlus size={30} />
          ) : (
            <KeyRound size={30} />
          )}
        </div>
        <p className="scene-kicker">SATRIA Command Center</p>

        {mode === 'loading' && <h2 id="auth-title">Memeriksa akun...</h2>}

        {mode === 'setup' && (
          <>
            <h2 id="auth-title">Buat akun admin</h2>
            <p className="import-copy">
              Belum ada akun terdaftar. Buat akun pertama dengan e-mail asli - langkah berikutnya mengaktifkan
              verifikasi dua langkah (MFA) yang wajib sebelum akun dapat digunakan.
            </p>
            {error && <p className="auth-error">{error}</p>}
            <form onSubmit={submitSetup}>
              <label className="auth-field">
                E-mail
                <input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="nama@organisasi.id" />
              </label>
              <label className="auth-field">
                Kata sandi
                <input type="password" required minLength={10} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Minimal 10 karakter" />
              </label>
              <label className="auth-field">
                Konfirmasi kata sandi
                <input type="password" required minLength={10} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
              </label>
              <div className="import-actions">
                <button className="primary-action" type="submit" disabled={busy}>
                  {busy ? <LoaderCircle className="spin" size={16} /> : <UserPlus size={16} />} Buat akun
                </button>
              </div>
            </form>
          </>
        )}

        {mode === 'enroll' && (
          <>
            <h2 id="auth-title">Aktifkan verifikasi dua langkah</h2>
            <p className="import-copy">
              Pindai kode QR ini dengan aplikasi authenticator (Google Authenticator, Authy, 1Password, dll), lalu
              masukkan kode 6 digit yang muncul.
            </p>
            {qrSvg && <div className="auth-qr" dangerouslySetInnerHTML={{ __html: qrSvg }} />}
            <p className="micro-copy">Tidak bisa memindai? Masukkan kunci ini secara manual sebagai akun "time-based" bernama SATRIA 2.0:</p>
            <div className="auth-secret">{secret.match(/.{1,4}/g)?.join(' ') ?? secret}</div>
            {error && <p className="auth-error">{error}</p>}
            <form onSubmit={submitEnroll}>
              <label className="auth-field">
                Kode verifikator
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]{6}"
                  required
                  maxLength={6}
                  value={totpCode}
                  onChange={(event) => setTotpCode(event.target.value)}
                  placeholder="123456"
                />
              </label>
              <div className="import-actions">
                <button className="primary-action" type="submit" disabled={busy}>
                  {busy ? <LoaderCircle className="spin" size={16} /> : <ShieldCheck size={16} />} Aktifkan dan masuk
                </button>
              </div>
            </form>
          </>
        )}

        {mode === 'login' && (
          <>
            <h2 id="auth-title">Masuk ke SATRIA</h2>
            <p className="import-copy">Masukkan e-mail, kata sandi, dan kode dari aplikasi authenticator Anda.</p>
            {error && <p className="auth-error">{error}</p>}
            <form onSubmit={submitLogin}>
              <label className="auth-field">
                E-mail
                <input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
              </label>
              <label className="auth-field">
                Kata sandi
                <input type="password" required value={password} onChange={(event) => setPassword(event.target.value)} />
              </label>
              <label className="auth-field">
                Kode verifikator
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]{6}"
                  required
                  maxLength={6}
                  value={totpCode}
                  onChange={(event) => setTotpCode(event.target.value)}
                  placeholder="123456"
                />
              </label>
              <label className="auth-remember">
                <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />
                Ingat saya
              </label>
              <div className="import-actions">
                <button className="primary-action" type="submit" disabled={busy}>
                  {busy ? <LoaderCircle className="spin" size={16} /> : <LogIn size={16} />} Masuk
                </button>
              </div>
            </form>
          </>
        )}
      </div>
    </section>
  )
}
