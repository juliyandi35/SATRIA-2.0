import { ContactShadows, PresentationControls } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { useSatriaStore } from '../store/useSatriaStore'
import type { MapPoint } from '../types'
import { AdaptiveQuality } from './AdaptiveQuality'
import { CameraRig } from './CameraRig'
import { Archipelago, DataNodes, PredictiveConstellation, RiskZones } from './IndonesiaMap'
import { IntelligenceCore } from './IntelligenceCore'
import { ParticleField } from './ParticleField'

const MIN_ZOOM = 0.35
const MAX_ZOOM = 1.6

export function World({ onSelectPoint }: { onSelectPoint: (point: MapPoint) => void }) {
  const zone = useSatriaStore((state) => state.zone)
  const [zoom, setZoom] = useState(1)
  const zoomRef = useRef(zoom)
  zoomRef.current = zoom
  const worldRef = useRef<HTMLDivElement>(null)

  // Scroll/pinch to zoom the map so tightly-clustered battalion nodes can be told apart and
  // clicked precisely, instead of being stuck at one fixed distance. Resets when the operator
  // switches zones so a close-up in one panel doesn't carry into the next. A native (non-passive)
  // listener is required because React's onWheel is passive by default and can't preventDefault -
  // without that, a trackpad pinch also triggers the browser's own page zoom alongside this one.
  useEffect(() => { setZoom(1) }, [zone])
  useEffect(() => {
    const node = worldRef.current
    if (!node) return
    const onWheel = (event: WheelEvent) => {
      event.preventDefault()
      const next = zoomRef.current * (1 + event.deltaY * 0.0012)
      setZoom(Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, next)))
    }
    node.addEventListener('wheel', onWheel, { passive: false })
    return () => node.removeEventListener('wheel', onWheel)
  }, [])
  const loaded = useSatriaStore((state) => state.loaded)
  const view = useSatriaStore((state) => state.view)
  const quality = useSatriaStore((state) => state.effectiveQuality)
  const spatial = useSatriaStore((state) => state.spatial)
  const spatialVisualMode = useSatriaStore((state) => state.spatialVisualMode)
  const predictive = useSatriaStore((state) => state.predictive)
  const aiActivity = useSatriaStore((state) => state.aiActivity)
  const visiblePoints = useMemo(() => {
    const points = view?.map_points ?? []
    if (zone !== 'spatial') return points
    return points.filter((point) => (point.readiness !== null && point.readiness < 80) || point.flagged_count > 0)
  }, [view?.map_points, zone])
  const showPoints = zone !== 'spatial' || spatialVisualMode !== 'clusters'
  const showClusters = zone === 'spatial' && spatialVisualMode !== 'points'

  return (
    <div className="world" aria-hidden="true" ref={worldRef}>
      <Canvas
        camera={{ position: [0, 4, 13], fov: 39, near: 0.1, far: 80 }}
        dpr={[1, 1.6]}
        gl={{ antialias: quality !== 'LOW', alpha: true, powerPreference: 'high-performance' }}
        shadows={quality === 'HIGH' || quality === 'ULTRA'}
        fallback={<div className="webgl-fallback" />}
      >
        <color attach="background" args={['#e8ebe5']} />
        <fog attach="fog" args={['#e8ebe5', 11, 31]} />
        <ambientLight intensity={1.7} color="#eef2ea" />
        <directionalLight position={[-6, 10, 8]} intensity={3.2} color="#fff2d6" castShadow={quality !== 'LOW'} />
        <directionalLight position={[8, 4, -5]} intensity={1.4} color="#b8ded8" />
        <Suspense fallback={null}>
          <ParticleField quality={quality} />
          <IntelligenceCore
            loaded={loaded}
            readiness={view?.summary.average_readiness ?? null}
            quality={quality}
            activity={aiActivity}
            zone={zone}
          />
          <PresentationControls
            global
            cursor
            enabled={loaded}
            speed={0.78}
            rotation={[0, 0, 0]}
            polar={[-0.32, 0.38]}
            azimuth={[-0.7, 0.7]}
            snap={false}
          >
            <group position={[2.4, -1.02, 0]}>
              <Archipelago quality={quality} />
              {loaded && view && showPoints && <DataNodes points={visiblePoints} quality={quality} onSelect={onSelectPoint} />}
              {loaded && spatial && showClusters && <RiskZones clusters={spatial.clusters} />}
              {loaded && zone === 'predictive' && predictive && <PredictiveConstellation risks={predictive.top_risks} />}
            </group>
          </PresentationControls>
          {(quality === 'HIGH' || quality === 'ULTRA') && (
            <ContactShadows position={[0, -1.03, 0]} opacity={0.18} scale={18} blur={2.6} far={5} resolution={quality === 'ULTRA' ? 1024 : 512} />
          )}
        </Suspense>
        <CameraRig zone={zone} zoom={zoom} />
        <AdaptiveQuality />
      </Canvas>
    </div>
  )
}
