import { Check, ChevronLeft, ChevronRight, Download, Pencil, Search, SlidersHorizontal, Upload, X } from 'lucide-react'
import { ChangeEvent, useCallback, useEffect, useRef, useState } from 'react'
import { Panel } from '../components/Panel'
import { api } from '../services/api'
import { useSatriaStore } from '../store/useSatriaStore'
import type { ActualRecord, DataView as DataViewType, ReferenceRecord } from '../types'

type Tab = 'readiness' | 'actual' | 'reference'
type Notify = (type: 'success' | 'error' | 'info', title: string, message: string) => void

const METRIC_COLUMNS: Array<{ key: keyof ActualRecord & keyof ReferenceRecord; label: string }> = [
  { key: 'personnel', label: 'Personnel' },
  { key: 'equipment', label: 'Equipment' },
  { key: 'logistics', label: 'Logistics' },
  { key: 'infrastructure', label: 'Infrastructure' },
  { key: 'training', label: 'Training' },
]

function readinessClass(readiness: number | null) {
  if (readiness === null) return ''
  if (readiness < 60) return 'value-critical'
  if (readiness < 80) return 'value-attention'
  return 'value-good'
}

export function DataView({ onError, onNotice }: { onError: (message: string) => void; onNotice: Notify }) {
  const [tab, setTab] = useState<Tab>('readiness')
  const view = useSatriaStore((state) => state.view)
  const filters = useSatriaStore((state) => state.filters)
  const setView = useSatriaStore((state) => state.setView)

  const refreshReadiness = useCallback(
    async (search: string, page: number, sortBy: string, sortOrder: 'asc' | 'desc') => {
      const result = (await api.dataView({ filters, search, page, page_size: 20, sort_by: sortBy, sort_order: sortOrder })) as DataViewType
      setView(result)
      return result
    },
    [filters, setView],
  )

  return (
    <Panel title="Akses data" description="Tabel aktual dan referensi MEF dapat diedit; tabel readiness selalu hasil hitung otomatis." wide>
      <div className="data-tabs-row">
        <div className="segmented-control data-tabs">
          <button className={tab === 'readiness' ? 'active' : ''} onClick={() => setTab('readiness')}>Tabel 3 · Readiness</button>
          <button className={tab === 'actual' ? 'active' : ''} onClick={() => setTab('actual')}>Tabel 1 · Aktual</button>
          <button className={tab === 'reference' ? 'active' : ''} onClick={() => setTab('reference')}>Tabel 2 · Referensi MEF</button>
        </div>
        <button className="quiet-action compact" onClick={() => { window.location.href = '/api/data/export' }}>
          <Download size={14} /> Export Dataset SATRIA
        </button>
      </div>
      {tab === 'readiness' && <ReadinessTable view={view} onError={onError} onNotice={onNotice} refreshReadiness={refreshReadiness} />}
      {tab === 'actual' && <ActualTable onError={onError} onNotice={onNotice} refreshReadiness={refreshReadiness} />}
      {tab === 'reference' && <ReferenceTable onError={onError} onNotice={onNotice} refreshReadiness={refreshReadiness} />}
    </Panel>
  )
}

function ReadinessTable({
  view,
  onError,
  onNotice,
  refreshReadiness,
}: {
  view: DataViewType | null
  onError: (message: string) => void
  onNotice: Notify
  refreshReadiness: (search: string, page: number, sortBy: string, sortOrder: 'asc' | 'desc') => Promise<DataViewType>
}) {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [sortBy, setSortBy] = useState('readiness')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')
  const [loading, setLoading] = useState(false)
  const [togglingId, setTogglingId] = useState<string | null>(null)
  const latestRequest = useRef(0)

  const toggleStatus = async (row: DataViewType['records'][number]) => {
    const target = row.status === 'FLAGGED' ? 'VERIFIED' : 'FLAGGED'
    setTogglingId(row.id)
    try {
      await api.overrideStatus(row.unit, row.location, row.category, target)
      onNotice('success', 'Status diperbarui', `${row.id} ditandai ${target}.`)
      await refreshReadiness(search, page, sortBy, sortOrder)
    } catch (error) {
      onNotice('error', 'Gagal mengubah status', error instanceof Error ? error.message : 'Status tidak dapat diubah.')
    } finally {
      setTogglingId(null)
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(async () => {
      const requestId = ++latestRequest.current
      setLoading(true)
      try {
        const result = await refreshReadiness(search, page, sortBy, sortOrder)
        if (requestId !== latestRequest.current) return
        if (result.pagination.page !== page) setPage(result.pagination.page)
      } catch (error) {
        if (requestId !== latestRequest.current) return
        onError(error instanceof Error ? error.message : 'Data tidak dapat dimuat.')
      } finally {
        if (requestId === latestRequest.current) setLoading(false)
      }
    }, 180)
    return () => window.clearTimeout(timer)
  }, [search, page, sortBy, sortOrder, refreshReadiness, onError])

  if (!view) return null
  const changeSort = (field: string) => {
    if (sortBy === field) setSortOrder((value) => (value === 'asc' ? 'desc' : 'asc'))
    else { setSortBy(field); setSortOrder('asc') }
  }

  return (
    <>
      <p className="micro-copy">Dihasilkan otomatis dari Tabel 1 x Tabel 2 (aktual / referensi MEF x 100). Klik status untuk menandai ulang FLAGGED/VERIFIED secara manual.</p>
      <div className="table-toolbar">
        <label><Search size={15} /><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} placeholder="Cari ID, unit, provinsi, atau kategori" /></label>
        <span><SlidersHorizontal size={14} /> {view.pagination.total_records.toLocaleString('id-ID')} hasil {loading && '· memuat'}</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr>
            <th><button onClick={() => changeSort('id')}>ID</button></th>
            <th><button onClick={() => changeSort('unit')}>Unit</button></th>
            <th><button onClick={() => changeSort('location')}>Provinsi</button></th>
            <th><button onClick={() => changeSort('category')}>Kategori</button></th>
            <th><button onClick={() => changeSort('readiness')}>Kesiapan</button></th>
            <th><button onClick={() => changeSort('status')}>Status</button></th>
            <th>Sinkronisasi</th>
          </tr></thead>
          <tbody>
            {view.records.map((row) => (
              <tr key={`${row.id}-${row.source_index}`}>
                <td>{row.id}</td><td>{row.unit}</td><td>{row.location}</td><td>{row.category}</td>
                <td><strong className={readinessClass(row.readiness)}>{row.readiness?.toFixed(1) ?? '—'}%</strong></td>
                <td>
                  <button
                    className={row.status === 'FLAGGED' ? 'status-chip flagged status-toggle' : 'status-chip status-toggle'}
                    onClick={() => toggleStatus(row)}
                    disabled={togglingId === row.id}
                    aria-label={`Ubah status ${row.id}`}
                  >
                    {togglingId === row.id ? '…' : row.status}
                  </button>
                </td>
                <td>{row.last_sync ? new Date(row.last_sync).toLocaleString('id-ID') : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pagination">
        <span>Halaman {view.pagination.page} dari {view.pagination.total_pages}</span>
        <div>
          <button disabled={page <= 1} onClick={() => setPage((value) => value - 1)} aria-label="Halaman sebelumnya"><ChevronLeft size={16} /></button>
          <button disabled={page >= view.pagination.total_pages} onClick={() => setPage((value) => value + 1)} aria-label="Halaman berikutnya"><ChevronRight size={16} /></button>
        </div>
      </div>
    </>
  )
}

function ActualTable({
  onError,
  onNotice,
  refreshReadiness,
}: {
  onError: (message: string) => void
  onNotice: Notify
  refreshReadiness: (search: string, page: number, sortBy: string, sortOrder: 'asc' | 'desc') => Promise<unknown>
}) {
  const [records, setRecords] = useState<ActualRecord[]>([])
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalRecords, setTotalRecords] = useState(0)
  const [loading, setLoading] = useState(false)
  const [editKey, setEditKey] = useState<string | null>(null)
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [importing, setImporting] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await api.dataActual(page, 20)
      setRecords(result.records)
      setTotalPages(result.pagination.total_pages)
      setTotalRecords(result.pagination.total_records)
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Data aktual tidak dapat dimuat.')
    } finally {
      setLoading(false)
    }
  }, [page, onError])

  useEffect(() => { load() }, [load])

  const rowKey = (row: ActualRecord) => `${row.unit_node}__${row.location}`

  const startEdit = (row: ActualRecord) => {
    setEditKey(rowKey(row))
    setDraft(Object.fromEntries(METRIC_COLUMNS.map(({ key }) => [key, String(row[key])])))
  }

  const saveEdit = async (row: ActualRecord) => {
    try {
      const fields = Object.fromEntries(METRIC_COLUMNS.map(({ key }) => [key, Number(draft[key])]))
      const result = await api.updateActual(row.unit_node, row.location, fields)
      setRecords((current) => current.map((item) => (rowKey(item) === rowKey(row) ? result.record : item)))
      setEditKey(null)
      onNotice('success', 'Data aktual diperbarui', `${row.unit_node} - readiness dihitung ulang otomatis.`)
      refreshReadiness('', 1, 'readiness', 'asc').catch(() => undefined)
    } catch (error) {
      onNotice('error', 'Gagal menyimpan', error instanceof Error ? error.message : 'Nilai tidak dapat disimpan.')
    }
  }

  const importCsv = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setImporting(true)
    try {
      const result = await api.importActual(file)
      onNotice('success', 'Data aktual diganti', `${result.rows.toLocaleString('id-ID')} baris dimuat, readiness dihitung ulang.`)
      setPage(1)
      await load()
      refreshReadiness('', 1, 'readiness', 'asc').catch(() => undefined)
    } catch (error) {
      onNotice('error', 'Impor gagal', error instanceof Error ? error.message : 'Berkas data aktual tidak dapat diimpor.')
    } finally {
      setImporting(false)
    }
  }

  return (
    <>
      <p className="micro-copy">Nilai kapabilitas nyata per unit. Ubah angka lalu simpan - tabel readiness ikut terhitung ulang otomatis.</p>
      <div className="table-toolbar">
        <span><SlidersHorizontal size={14} /> {totalRecords.toLocaleString('id-ID')} unit {loading && '· memuat'}</span>
        <button className="quiet-action compact" onClick={() => fileInput.current?.click()} disabled={importing}>
          <Upload size={14} /> {importing ? 'Mengimpor…' : 'Impor CSV/XLSX aktual'}
        </button>
        <input ref={fileInput} type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" hidden onChange={importCsv} />
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr>
            <th>Unit</th><th>Tipe</th><th>Provinsi</th>
            {METRIC_COLUMNS.map(({ key, label }) => <th key={key}>{label}</th>)}
            <th></th>
          </tr></thead>
          <tbody>
            {records.map((row) => {
              const editing = editKey === rowKey(row)
              return (
                <tr key={rowKey(row)}>
                  <td>{row.unit_node}</td><td>{row.unit_type}</td><td>{row.location}</td>
                  {METRIC_COLUMNS.map(({ key }) => (
                    <td key={key}>
                      {editing ? (
                        <input
                          className="cell-input"
                          type="number"
                          min={0}
                          value={draft[key] ?? ''}
                          onChange={(event) => setDraft((current) => ({ ...current, [key]: event.target.value }))}
                        />
                      ) : (
                        row[key].toLocaleString('id-ID')
                      )}
                    </td>
                  ))}
                  <td>
                    {editing ? (
                      <div className="row-edit-actions">
                        <button className="icon-button" onClick={() => saveEdit(row)} aria-label={`Simpan ${row.unit_node}`}><Check size={14} /></button>
                        <button className="icon-button" onClick={() => setEditKey(null)} aria-label="Batal"><X size={14} /></button>
                      </div>
                    ) : (
                      <button className="icon-button" onClick={() => startEdit(row)} aria-label={`Edit ${row.unit_node}`}><Pencil size={14} /></button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="pagination">
        <span>Halaman {page} dari {totalPages}</span>
        <div>
          <button disabled={page <= 1} onClick={() => setPage((value) => value - 1)} aria-label="Halaman sebelumnya"><ChevronLeft size={16} /></button>
          <button disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)} aria-label="Halaman berikutnya"><ChevronRight size={16} /></button>
        </div>
      </div>
    </>
  )
}

function ReferenceTable({
  onError,
  onNotice,
  refreshReadiness,
}: {
  onError: (message: string) => void
  onNotice: Notify
  refreshReadiness: (search: string, page: number, sortBy: string, sortOrder: 'asc' | 'desc') => Promise<unknown>
}) {
  const [records, setRecords] = useState<ReferenceRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [editKey, setEditKey] = useState<string | null>(null)
  const [draft, setDraft] = useState<Record<string, string>>({})

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await api.dataReference()
      setRecords(result.records)
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Referensi MEF tidak dapat dimuat.')
    } finally {
      setLoading(false)
    }
  }, [onError])

  useEffect(() => { load() }, [load])

  const startEdit = (row: ReferenceRecord) => {
    setEditKey(row.unit_type)
    setDraft(Object.fromEntries(METRIC_COLUMNS.map(({ key }) => [key, String(row[key])])))
  }

  const saveEdit = async (row: ReferenceRecord) => {
    try {
      const fields = Object.fromEntries(METRIC_COLUMNS.map(({ key }) => [key, Number(draft[key])]))
      const result = await api.updateReference(row.unit_type, fields)
      setRecords((current) => current.map((item) => (item.unit_type === row.unit_type ? result.record : item)))
      setEditKey(null)
      onNotice('success', 'Referensi MEF diperbarui', `${row.unit_type} - setiap unit tipe ini terhitung ulang otomatis.`)
      refreshReadiness('', 1, 'readiness', 'asc').catch(() => undefined)
    } catch (error) {
      onNotice('error', 'Gagal menyimpan', error instanceof Error ? error.message : 'Nilai tidak dapat disimpan.')
    }
  }

  return (
    <>
      <p className="micro-copy">Standar Minimum Essential Force per tipe unit - acuan pembagi perhitungan readiness. Enam tipe unit, jarang berubah.</p>
      <div className="table-toolbar">
        <span><SlidersHorizontal size={14} /> {records.length} tipe unit {loading && '· memuat'}</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr>
            <th>Tipe unit</th>
            {METRIC_COLUMNS.map(({ key, label }) => <th key={key}>{label}</th>)}
            <th></th>
          </tr></thead>
          <tbody>
            {records.map((row) => {
              const editing = editKey === row.unit_type
              return (
                <tr key={row.unit_type}>
                  <td>{row.unit_type}</td>
                  {METRIC_COLUMNS.map(({ key }) => (
                    <td key={key}>
                      {editing ? (
                        <input
                          className="cell-input"
                          type="number"
                          min={1}
                          value={draft[key] ?? ''}
                          onChange={(event) => setDraft((current) => ({ ...current, [key]: event.target.value }))}
                        />
                      ) : (
                        row[key].toLocaleString('id-ID')
                      )}
                    </td>
                  ))}
                  <td>
                    {editing ? (
                      <div className="row-edit-actions">
                        <button className="icon-button" onClick={() => saveEdit(row)} aria-label={`Simpan ${row.unit_type}`}><Check size={14} /></button>
                        <button className="icon-button" onClick={() => setEditKey(null)} aria-label="Batal"><X size={14} /></button>
                      </div>
                    ) : (
                      <button className="icon-button" onClick={() => startEdit(row)} aria-label={`Edit ${row.unit_type}`}><Pencil size={14} /></button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}
