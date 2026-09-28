import { DatabaseZap, FileUp, LoaderCircle } from 'lucide-react'
import { useRef, useState } from 'react'
import { useSatriaStore } from '../store/useSatriaStore'

export function ImportGate({
  onBuiltin,
  onFile,
}: {
  onBuiltin: () => void
  onFile: (file: File) => void
}) {
  const loaded = useSatriaStore((state) => state.loaded)
  const importing = useSatriaStore((state) => state.importing)
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  if (loaded) return null

  const acceptFile = (file?: File) => {
    if (file) onFile(file)
  }

  return (
    <section
      className={dragging ? 'import-gate dragging' : 'import-gate'}
      aria-labelledby="empty-state-title"
      onDragOver={(event) => {
        event.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault()
        setDragging(false)
        acceptFile(event.dataTransfer.files[0])
      }}
    >
      <div className="import-emblem">
        {importing ? <LoaderCircle className="spin" size={34} /> : <DatabaseZap size={34} />}
      </div>
      <p className="scene-kicker">Nusantara Intelligence Core</p>
      <h2 id="empty-state-title">Menunggu data kesiapan</h2>
      <p className="import-copy">
        Lingkungan telah siap. Muat dataset agar geografi, analitik, risiko, dan SATRIA AI menerima satu sumber data yang sama.
      </p>
      {importing ? (
        <div className="import-progress" role="status">
          <span />
          Membaca, memvalidasi, dan menyiapkan analisis…
        </div>
      ) : (
        <div className="import-actions">
          <button className="primary-action" onClick={onBuiltin}>
            <DatabaseZap size={17} /> Gunakan data terakhir
          </button>
          <button className="quiet-action" onClick={() => input.current?.click()}>
            <FileUp size={17} /> Impor data aktual lain
          </button>
          <input
            ref={input}
            type="file"
            accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            hidden
            onChange={(event) => { acceptFile(event.target.files?.[0]); event.target.value = '' }}
          />
        </div>
      )}
      <p className="import-note">
        "Gunakan data terakhir" memuat data aktual tersimpan. Mengimpor berkas CSV/XLSX lain menggantikan seluruh data aktual.
      </p>
    </section>
  )
}
