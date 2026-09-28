import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'
import { useEffect } from 'react'

export type Notice = { id: number; type: 'success' | 'error' | 'info'; title: string; message: string }

export function Notification({ notice, onClose }: { notice: Notice | null; onClose: () => void }) {
  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(onClose, 5000)
    return () => window.clearTimeout(timer)
  }, [notice, onClose])

  if (!notice) return null
  const Icon = notice.type === 'success' ? CheckCircle2 : notice.type === 'error' ? AlertTriangle : Info
  return (
    <div className={`notice ${notice.type}`} role={notice.type === 'error' ? 'alert' : 'status'}>
      <Icon size={19} />
      <div><strong>{notice.title}</strong><span>{notice.message}</span></div>
      <button onClick={onClose} aria-label="Tutup notifikasi"><X size={15} /></button>
      <i className="notice-timer" aria-hidden="true" />
    </div>
  )
}
