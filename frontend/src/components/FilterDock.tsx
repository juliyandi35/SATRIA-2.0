import { SlidersHorizontal, X } from 'lucide-react'
import { useState } from 'react'
import { SatriaSelect } from './SatriaSelect'
import { useSatriaStore } from '../store/useSatriaStore'
import type { Filters } from '../types'

export function FilterDock() {
  const loaded = useSatriaStore((state) => state.loaded)
  const view = useSatriaStore((state) => state.view)
  const filters = useSatriaStore((state) => state.filters)
  const setFilters = useSatriaStore((state) => state.setFilters)
  const [open, setOpen] = useState(false)
  if (!loaded || !view) return null

  const fields: Array<{ key: keyof Filters; label: string; values: string[]; allLabel?: string }> = [
    { key: 'location', label: 'Provinsi', values: view.filter_options.location },
    { key: 'category', label: 'Kategori', values: view.filter_options.category },
    { key: 'status', label: 'Status', values: view.filter_options.status },
    { key: 'satuan', label: 'Satuan', values: view.filter_options.satuan },
    { key: 'unit', label: 'Unit', values: view.filter_options.unit },
  ]
  const activeCount = Object.values(filters).filter(Boolean).length

  return (
    <div className={open ? 'filter-dock open' : 'filter-dock'}>
      <button className="filter-trigger" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
        <SlidersHorizontal size={16} />
        Filter lintas-zona
        {activeCount > 0 && <b>{activeCount}</b>}
      </button>
      {open && (
        <div className="filter-sheet">
          <div className="sheet-heading">
            <div><strong>Ruang analisis aktif</strong><span>Perubahan berlaku pada seluruh zona.</span></div>
            <button className="icon-button" onClick={() => setOpen(false)} aria-label="Tutup filter"><X size={16} /></button>
          </div>
          <div className="filter-grid">
            {fields.map((field) => (
              <div className="filter-field" key={field.key}>
                <span>{field.label}</span>
                <SatriaSelect
                  value={(filters[field.key] as string) || ''}
                  ariaLabel={`Filter ${field.label}`}
                  options={[{ value: '', label: 'Semua' }, ...field.values.map((value) => ({ value, label: value }))]}
                  onChange={(value) => {
                    const next = { ...filters, [field.key]: value || undefined }
                    if (field.key === 'satuan') next.unit = undefined
                    setFilters(next)
                  }}
                />
              </div>
            ))}
            <div className="filter-field">
              <span>Lensa risiko</span>
              <SatriaSelect
                value={filters.risk || ''}
                ariaLabel="Filter lensa risiko"
                options={[
                  { value: '', label: 'Semua observasi' },
                  { value: 'good', label: 'Baik' },
                  { value: 'attention', label: 'Kurang' },
                  { value: 'critical', label: 'Kritis' },
                ]}
                onChange={(value) => setFilters({ ...filters, risk: value || undefined })}
              />
            </div>
          </div>
          {activeCount > 0 && <button className="text-action" onClick={() => setFilters({})}>Hapus semua filter</button>}
        </div>
      )}
    </div>
  )
}
