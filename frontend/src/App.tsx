import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { CommandRail } from './components/CommandRail'
import { FilterDock } from './components/FilterDock'
import { ImportGate } from './components/ImportGate'
import { LoginGate } from './components/LoginGate'
import { MetricRibbon } from './components/MetricRibbon'
import { Notification, type Notice } from './components/Notification'
import { TopBar } from './components/TopBar'
import { WelcomeGate } from './components/WelcomeGate'
import { World } from './experience/World'
import { api } from './services/api'
import { useSatriaStore } from './store/useSatriaStore'
import type { DataView, MapPoint, ModelStatus, PredictiveResult, SpatialResult } from './types'
import { CommandView } from './views/CommandView'
import { MapView } from './views/MapView'

const ReadinessView = lazy(() => import('./views/ReadinessView').then((module) => ({ default: module.ReadinessView })))
const SpatialView = lazy(() => import('./views/SpatialView').then((module) => ({ default: module.SpatialView })))
const PredictiveView = lazy(() => import('./views/PredictiveView').then((module) => ({ default: module.PredictiveView })))
const DiagnosticsView = lazy(() => import('./views/DiagnosticsView').then((module) => ({ default: module.DiagnosticsView })))
const DataTableView = lazy(() => import('./views/DataView').then((module) => ({ default: module.DataView })))
const AIView = lazy(() => import('./views/AIView').then((module) => ({ default: module.AIView })))
const SystemView = lazy(() => import('./views/SystemView').then((module) => ({ default: module.SystemView })))

function supportsWebGL() {
  try {
    const canvas = document.createElement('canvas')
    return Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl'))
  } catch {
    return false
  }
}

export default function App() {
  const zone = useSatriaStore((state) => state.zone)
  const loaded = useSatriaStore((state) => state.loaded)
  const filters = useSatriaStore((state) => state.filters)
  const selectedModel = useSatriaStore((state) => state.selectedModel)
  const setFilters = useSatriaStore((state) => state.setFilters)
  const setZone = useSatriaStore((state) => state.setZone)
  const setLoaded = useSatriaStore((state) => state.setLoaded)
  const setImporting = useSatriaStore((state) => state.setImporting)
  const setMetadata = useSatriaStore((state) => state.setMetadata)
  const setView = useSatriaStore((state) => state.setView)
  const setSpatial = useSatriaStore((state) => state.setSpatial)
  const setPredictive = useSatriaStore((state) => state.setPredictive)
  const setDiagnostics = useSatriaStore((state) => state.setDiagnostics)
  const setModels = useSatriaStore((state) => state.setModels)
  const setSystem = useSatriaStore((state) => state.setSystem)
  const [booting, setBooting] = useState(true)
  const [entered, setEntered] = useState(false)
  const [authState, setAuthState] = useState<'checking' | 'guest' | 'authed'>('checking')
  const [accountEmail, setAccountEmail] = useState<string | null>(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [notice, setNotice] = useState<Notice | null>(null)
  const [webgl] = useState(supportsWebGL)
  const viewRequest = useRef(0)
  const spatialRequest = useRef(0)
  const predictiveRequest = useRef(0)
  const diagnosticsRequest = useRef(0)

  const notify = useCallback((type: Notice['type'], title: string, message: string) => {
    setNotice({ id: Date.now(), type, title, message })
  }, [])
  const closeNotice = useCallback(() => setNotice(null), [])
  const enterCommandCenter = useCallback(() => setEntered(true), [])
  const showError = useCallback((message: string) => notify('error', 'Permintaan tidak selesai', message), [notify])

  const loadView = useCallback(async () => {
    const requestId = ++viewRequest.current
    const result = await api.dataView({ filters, page: 1, page_size: 20, sort_by: 'readiness', sort_order: 'asc' }) as DataView
    if (requestId === viewRequest.current) setView(result)
    return result
  }, [filters, setView])

  const loadSpatial = useCallback(async () => {
    const requestId = ++spatialRequest.current
    setAnalysisLoading(true)
    try {
      const result = await api.spatial(filters) as SpatialResult
      if (requestId === spatialRequest.current) setSpatial(result)
    } catch (error) {
      if (requestId === spatialRequest.current) showError(error instanceof Error ? error.message : 'Klaster spasial gagal dihitung.')
    } finally {
      if (requestId === spatialRequest.current) setAnalysisLoading(false)
    }
  }, [filters, setSpatial, showError])

  const loadPredictive = useCallback(async () => {
    const requestId = ++predictiveRequest.current
    setAnalysisLoading(true)
    try {
      const result = await api.predictive(filters) as PredictiveResult
      if (requestId === predictiveRequest.current) setPredictive(result)
    } catch (error) {
      if (requestId === predictiveRequest.current) showError(error instanceof Error ? error.message : 'Risiko tersembunyi gagal dihitung.')
    } finally {
      if (requestId === predictiveRequest.current) setAnalysisLoading(false)
    }
  }, [filters, setPredictive, showError])

  const loadDiagnostics = useCallback(async () => {
    const requestId = ++diagnosticsRequest.current
    setAnalysisLoading(true)
    try {
      const result = await api.diagnostics(filters) as Record<string, any>
      if (requestId === diagnosticsRequest.current) setDiagnostics(result)
    } catch (error) {
      if (requestId === diagnosticsRequest.current) showError(error instanceof Error ? error.message : 'Diagnostik gagal dijalankan.')
    } finally {
      if (requestId === diagnosticsRequest.current) setAnalysisLoading(false)
    }
  }, [filters, setDiagnostics, showError])

  useEffect(() => {
    let active = true
    api.auth
      .session()
      .then((result) => {
        if (!active) return
        if (result.authenticated) { setAccountEmail(result.email); setAuthState('authed') }
        else setAuthState('guest')
      })
      .catch(() => { if (active) setAuthState('guest') })
    return () => { active = false }
  }, [])

  useEffect(() => {
    const handleUnauthorized = () => { setAuthState('guest'); setEntered(false); setBooting(true) }
    window.addEventListener('satria:unauthorized', handleUnauthorized)
    return () => window.removeEventListener('satria:unauthorized', handleUnauthorized)
  }, [])

  const logout = useCallback(async () => {
    try { await api.auth.logout() } catch { /* session already gone */ }
    setAccountEmail(null)
    setEntered(false)
    setBooting(true)
    setAuthState('guest')
  }, [])

  useEffect(() => {
    if (authState !== 'authed') return
    let active = true
    Promise.allSettled([api.dataStatus(), api.models(), api.systemStatus()]).then((results) => {
      if (!active) return
      const [dataResult, modelResult, systemResult] = results
      if (dataResult.status === 'fulfilled') {
        const status = dataResult.value as any
        setLoaded(Boolean(status.loaded))
        setMetadata(status.metadata ?? null)
      } else {
        showError('Backend SATRIA belum dapat dijangkau.')
      }
      if (modelResult.status === 'fulfilled') setModels(modelResult.value.models as ModelStatus[])
      if (systemResult.status === 'fulfilled') setSystem(systemResult.value)
      setBooting(false)
    })
    return () => { active = false }
  }, [authState, setLoaded, setMetadata, setModels, setSystem, showError])

  useEffect(() => {
    if (!loaded) return
    loadView().catch((error) => showError(error instanceof Error ? error.message : String(error)))
  }, [loaded, filters, loadView, showError])

  useEffect(() => {
    if (!loaded) return
    if (zone === 'spatial') loadSpatial()
    if (zone === 'predictive') loadPredictive()
    if (zone === 'diagnostics') loadDiagnostics()
    if (zone === 'system') api.systemStatus().then(setSystem).catch(() => undefined)
  }, [loaded, zone, filters, loadSpatial, loadPredictive, loadDiagnostics, setSystem])

  const importDataset = async (file?: File) => {
    setImporting(true)
    try {
      const result: any = file ? await api.importActual(file) : await api.importBuiltin()
      setMetadata(result.metadata)
      setLoaded(true)
      setFilters({})
      const view = await api.dataView({ filters: {}, page: 1, page_size: 20, sort_by: 'readiness', sort_order: 'asc' }) as DataView
      setView(view)
      notify('success', 'Dataset siap', `${result.metadata.rows.toLocaleString('id-ID')} baris tervalidasi dan terhubung ke seluruh zona.`)
    } catch (error) {
      showError(error instanceof Error ? error.message : 'Dataset tidak dapat diimpor.')
    } finally {
      setImporting(false)
    }
  }

  const resetData = async () => {
    try {
      await api.resetData()
      setLoaded(false); setMetadata(null); setView(null); setSpatial(null); setPredictive(null); setDiagnostics(null); setFilters({}); setZone('command')
      notify('info', 'Dataset dilepas', 'Lingkungan kembali ke keadaan menunggu data. Berkas sumber tidak diubah.')
    } catch (error) { showError(error instanceof Error ? error.message : 'Dataset tidak dapat dilepas.') }
  }

  const selectPoint = (point: MapPoint) => {
    const satuan = point.unit.trim().split(/\s+/)[0]
    setFilters({ ...filters, location: point.location, unit: point.unit, satuan })
    setZone('readiness')
    notify('info', point.unit, `Fokus dipindahkan ke ${point.location}.`)
  }

  const activeView = () => {
    if (!loaded) return null
    switch (zone) {
      case 'command': return <CommandView />
      case 'map': return <MapView />
      case 'readiness': return <ReadinessView />
      case 'spatial': return <SpatialView loading={analysisLoading} onRefresh={loadSpatial} />
      case 'predictive': return <PredictiveView loading={analysisLoading} onRefresh={loadPredictive} />
      case 'diagnostics': return <DiagnosticsView loading={analysisLoading} onRefresh={loadDiagnostics} />
      case 'data': return <DataTableView onError={showError} onNotice={notify} />
      case 'ai': return <AIView onError={showError} />
      case 'system': return <SystemView onNotice={notify} onReset={resetData} onLogout={logout} accountEmail={accountEmail} onEmailChanged={setAccountEmail} />
    }
  }

  if (authState === 'checking') {
    return <div className="boot-screen"><div className="boot-symbol">S</div><span>Memeriksa sesi keamanan</span><i /></div>
  }

  if (authState === 'guest') {
    return <LoginGate onAuthenticated={(email) => { setAccountEmail(email); setAuthState('authed') }} />
  }

  if (booting) {
    return <div className="boot-screen"><div className="boot-symbol">S</div><span>Menginisialisasi lingkungan SATRIA</span><i /></div>
  }

  return (
    <main className={`${loaded ? 'app-shell data-awake' : 'app-shell'} ${entered ? '' : 'awaiting-entry'}`.trim()}>
      {webgl ? <World onSelectPoint={selectPoint} /> : <div className="webgl-fallback"><span>Mode visual tereduksi</span></div>}
      <div className="topographic-veil" aria-hidden="true" />
      {!entered ? <WelcomeGate loaded={loaded} model={selectedModel} onEnter={enterCommandCenter} /> : <>
        <CommandRail />
        <TopBar />
        <div className="spatial-interface" key={zone}><Suspense fallback={<div className="panel-loading">Menyiapkan zona…</div>}>{activeView()}</Suspense></div>
        <ImportGate onBuiltin={() => importDataset()} onFile={(file) => importDataset(file)} />
        <MetricRibbon />
        <FilterDock />
        {!webgl && <div className="fallback-note">WebGL tidak tersedia. Analitik dan SATRIA AI tetap dapat digunakan.</div>}
      </>}
      <Notification notice={notice} onClose={closeNotice} />
    </main>
  )
}
