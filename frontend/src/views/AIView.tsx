import { Bot, Eraser, Mail, Send, Sparkles } from 'lucide-react'
import { FormEvent, useState } from 'react'
import { MarkdownMessage } from '../components/MarkdownMessage'
import { Panel } from '../components/Panel'
import { SatriaSelect } from '../components/SatriaSelect'
import { api } from '../services/api'
import { useSatriaStore } from '../store/useSatriaStore'
import type { ChatMessage } from '../types'

const starterPrompts = [
  'Ringkas kondisi kesiapan pada filter aktif.',
  'Jelaskan unit dengan kesiapan terendah.',
  'Apa masalah kualitas data yang perlu diperhatikan?',
]

export function AIView({ onError }: { onError: (message: string) => void }) {
  const view = useSatriaStore((state) => state.view)
  const filters = useSatriaStore((state) => state.filters)
  const models = useSatriaStore((state) => state.models)
  const selectedModel = useSatriaStore((state) => state.selectedModel)
  const setSelectedModel = useSatriaStore((state) => state.setSelectedModel)
  const localOnly = useSatriaStore((state) => state.localOnly)
  const auditLog = useSatriaStore((state) => state.auditLog)
  const setAiActivity = useSatriaStore((state) => state.setAiActivity)
  const messages = useSatriaStore((state) => state.chatMessages)
  const sessionId = useSatriaStore((state) => state.chatSessionId)
  const appendChatMessage = useSatriaStore((state) => state.appendChatMessage)
  const clearChatMessages = useSatriaStore((state) => state.clearChatMessages)
  const emailConfigured = useSatriaStore((state) => Boolean(state.system?.email?.configured))
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [reportEmailOpen, setReportEmailOpen] = useState(false)
  const [reportEmail, setReportEmail] = useState('')

  const send = async (event?: FormEvent, prompt?: string) => {
    event?.preventDefault()
    const message = (prompt ?? input).trim()
    if (!message || sending) return
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', content: message }
    appendChatMessage(userMessage)
    setInput('')
    setSending(true)
    setAiActivity('thinking')
    try {
      const result = await api.chat({
        message,
        session_id: sessionId,
        active_unit: filters.unit || 'National',
        selected_region: filters.location || 'All',
        context: {
          filters,
          active_zone: 'ai',
          summary: view?.summary,
          local_exec: localOnly,
          audit_log: auditLog,
          ai_model: selectedModel,
        },
      })
      appendChatMessage({ id: crypto.randomUUID(), role: 'assistant', content: result.response })
      setAiActivity('answering')
      window.setTimeout(() => setAiActivity('idle'), 700)
    } catch (error) {
      setAiActivity('error')
      onError(error instanceof Error ? error.message : 'SATRIA AI tidak merespons.')
    } finally {
      setSending(false)
    }
  }

  const clear = async () => {
    await api.clearChat(sessionId).catch(() => undefined)
    clearChatMessages()
    setAiActivity('idle')
  }

  const sendFullReport = (event: FormEvent) => {
    event.preventDefault()
    send(undefined, `Buatkan laporan lengkap kesiapan dalam format PDF dan kirimkan ke ${reportEmail}.`)
    setReportEmailOpen(false)
    setReportEmail('')
  }

  return (
    <Panel title="SATRIA AI" description="Asisten lokal menerima ringkasan terstruktur dari filter dan analisis aktif, bukan salinan ribuan baris." wide>
      <div className="ai-shell">
        <div className="ai-toolbar">
          <SatriaSelect
            className="model-select"
            value={selectedModel}
            onChange={setSelectedModel}
            ariaLabel="Model SATRIA AI"
            icon={<Bot size={15} />}
            options={models.map((model) => ({ value: model.name, label: `${model.name}${model.available ? '' : ' — tidak tersedia'}`, disabled: !model.available }))}
          />
          <span className="privacy-badge">{localOnly ? 'Mode lokal' : 'Tool eksternal diizinkan'}</span>
          <button className="icon-button" onClick={clear} aria-label="Hapus percakapan"><Eraser size={16} /></button>
        </div>
        <div className="brief-action">
          <button className="text-action" onClick={() => setReportEmailOpen((value) => !value)}><Mail size={14} /> Kirim laporan lengkap via e-mail</button>
          {reportEmailOpen && (emailConfigured && !localOnly ? (
            <form onSubmit={sendFullReport}><input type="email" required value={reportEmail} onChange={(event) => setReportEmail(event.target.value)} placeholder="penerima@organisasi.id" aria-label="Email penerima laporan lengkap" /><button type="submit" disabled={sending} aria-label="Kirim laporan lengkap"><Send size={14} /></button></form>
          ) : <span>{!emailConfigured ? 'Konfigurasikan SMTP di environment terlebih dahulu.' : 'Nonaktifkan mode lokal untuk mengizinkan pengiriman email.'}</span>)}
        </div>
        <div className="chat-stream" aria-live="polite">
          {messages.length === 0 ? (
            <div className="ai-empty"><Sparkles size={26} /><h3>Siap memberi briefing</h3><p>Pilih arahan atau ajukan pertanyaan terhadap keadaan visual saat ini.</p><div>{starterPrompts.map((prompt) => <button key={prompt} onClick={() => send(undefined, prompt)}>{prompt}</button>)}</div></div>
          ) : messages.map((message) => (
            <article key={message.id} className={message.role}>
              <span>{message.role === 'assistant' ? 'SATRIA' : 'Anda'}</span>
              {message.role === 'assistant' ? <MarkdownMessage content={message.content} /> : <p>{message.content}</p>}
            </article>
          ))}
          {sending && <article className="assistant thinking"><span>SATRIA</span><p>Menelaah konteks aktif…</p></article>}
        </div>
        <form className="chat-composer" onSubmit={(event) => send(event)}>
          <textarea value={input} onChange={(event) => setInput(event.target.value)} placeholder="Tanyakan kondisi, risiko, atau kualitas data…" rows={2} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); send() } }} />
          <button type="submit" disabled={!input.trim() || sending} aria-label="Kirim pesan"><Send size={17} /></button>
        </form>
      </div>
    </Panel>
  )
}
