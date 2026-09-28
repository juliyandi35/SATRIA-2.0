import { Edges, Html, Line } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { Crosshair } from 'lucide-react'
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import type { Cluster, EffectiveQuality, MapPoint, RiskItem } from '../types'

type GeoJson = {
  features: Array<{ geometry: { type: string; coordinates: any }; properties: Record<string, unknown> }>
}

const projectFlat = (lon: number, lat: number): [number, number] => [(lon - 118) * 0.24, (lat + 2.5) * 0.24]
const projectWorld = (lon: number, lat: number): [number, number, number] => {
  const [x, y] = projectFlat(lon, lat)
  return [x, 0.16, -y]
}

function polygonRings(geometry: GeoJson['features'][number]['geometry']): number[][][] {
  if (geometry.type === 'Polygon') return geometry.coordinates as number[][][]
  if (geometry.type === 'MultiPolygon') return (geometry.coordinates as number[][][][]).flatMap((polygon) => [polygon[0]])
  return []
}

export function Archipelago({ quality }: { quality: EffectiveQuality }) {
  const [geojson, setGeojson] = useState<GeoJson | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/geography/provinces', { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error('GeoJSON unavailable'))))
      .then(setGeojson)
      .catch(() => undefined)
    return () => controller.abort()
  }, [])

  const shapes = useMemo(() => {
    if (!geojson || quality === 'LOW') return []
    const step = quality === 'MEDIUM' ? 4 : quality === 'HIGH' ? 2 : 1
    const result: THREE.Shape[] = []
    for (const feature of geojson.features) {
      for (const ring of polygonRings(feature.geometry)) {
        if (ring.length < 4) continue
        const shape = new THREE.Shape()
        ring.forEach(([lon, lat], index) => {
          if (index % step !== 0 && index !== ring.length - 1) return
          const [x, y] = projectFlat(lon, lat)
          if (index === 0) shape.moveTo(x, y)
          else shape.lineTo(x, y)
        })
        result.push(shape)
      }
    }
    return result
  }, [geojson, quality])

  const lowLines = useMemo(() => {
    if (!geojson || quality !== 'LOW') return new Float32Array()
    const values: number[] = []
    for (const feature of geojson.features) {
      for (const ring of polygonRings(feature.geometry)) {
        const sampled = ring.filter((_, index) => index % 12 === 0 || index === ring.length - 1)
        for (let index = 0; index < sampled.length - 1; index++) {
          const [x1, y1] = projectFlat(sampled[index][0], sampled[index][1])
          const [x2, y2] = projectFlat(sampled[index + 1][0], sampled[index + 1][1])
          values.push(x1, y1, 0, x2, y2, 0)
        }
      }
    }
    return new Float32Array(values)
  }, [geojson, quality])

  if (quality === 'LOW' && lowLines.length) {
    return (
      <lineSegments rotation={[-Math.PI / 2, 0, 0]}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[lowLines, 3]} />
        </bufferGeometry>
        <lineBasicMaterial color="#688079" transparent opacity={0.62} />
      </lineSegments>
    )
  }
  if (!shapes.length) return null
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow={quality !== 'LOW'}>
      <extrudeGeometry args={[shapes, { depth: quality === 'ULTRA' ? 0.13 : 0.07, bevelEnabled: false, curveSegments: 1 }]} />
      <meshStandardMaterial color="#cbd7d1" roughness={0.68} metalness={0.08} transparent opacity={0.92} />
      <Edges color="#688079" threshold={18} opacity={0.48} transparent />
    </mesh>
  )
}

function nodeColor(readiness: number | null, flagged: number) {
  if (flagged > 0 || (readiness !== null && readiness < 60)) return new THREE.Color('#9b3d36')
  if (readiness !== null && readiness < 80) return new THREE.Color('#a77b45')
  return new THREE.Color('#17666a')
}

export function DataNodes({ points, quality, onSelect }: { points: MapPoint[]; quality: EffectiveQuality; onSelect: (point: MapPoint) => void }) {
  const ref = useRef<THREE.InstancedMesh>(null)
  const hitRef = useRef<THREE.InstancedMesh>(null)
  const [hovered, setHovered] = useState<number | null>(null)
  const [pinned, setPinned] = useState<number | null>(null)
  const pinTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const visiblePoints = useMemo(() => points.slice(0, quality === 'LOW' ? 120 : quality === 'MEDIUM' ? 360 : 650), [points, quality])

  // Two different gaps stand between "hover shows the panel" and "click Inspeksi", and each
  // needs its own fix. (1) The panel is bigger than, and offset from, the tiny point mesh, so
  // the cursor leaves the mesh's raycast hit area for a brief instant while still travelling
  // onto the panel - a short grace window (cancelled once the panel's own pointer events confirm
  // the cursor arrived) bridges that. (2) Reaching "Inspeksi" from there is a second, deliberate
  // move the operator makes at their own pace, so clicking anywhere on the panel first pins it
  // open for a full 10 seconds - immune to any further hover changes - to give that time.
  const clearHideTimer = () => {
    if (hideTimer.current !== null) { clearTimeout(hideTimer.current); hideTimer.current = null }
  }
  const scheduleHide = () => {
    clearHideTimer()
    hideTimer.current = setTimeout(() => setHovered(null), 350)
  }
  const clearPinTimer = () => {
    if (pinTimer.current !== null) { clearTimeout(pinTimer.current); pinTimer.current = null }
  }
  const pin = (index: number) => {
    clearHideTimer()
    clearPinTimer()
    setPinned(index)
    pinTimer.current = setTimeout(() => { setPinned(null); pinTimer.current = null }, 10000)
  }
  useEffect(() => () => { clearHideTimer(); clearPinTimer() }, [])

  useLayoutEffect(() => {
    if (!ref.current || !hitRef.current) return
    const transform = new THREE.Object3D()
    visiblePoints.forEach((point, index) => {
      const raw = point.readiness ?? 0
      const visualHeight = 0.18 + Math.min(1.65, Math.abs(100 - raw) * 0.025)
      const [x, y, z] = projectWorld(point.lon, point.lat)
      transform.position.set(x, y + visualHeight / 2, z)
      transform.scale.set(1, visualHeight, 1)
      transform.updateMatrix()
      ref.current!.setMatrixAt(index, transform.matrix)
      ref.current!.setColorAt(index, nodeColor(point.readiness, point.flagged_count))
      hitRef.current!.setMatrixAt(index, transform.matrix)
    })
    ref.current.instanceMatrix.needsUpdate = true
    if (ref.current.instanceColor) ref.current.instanceColor.needsUpdate = true
    hitRef.current.instanceMatrix.needsUpdate = true
  }, [visiblePoints])

  useFrame((state) => {
    if (ref.current) ref.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.12) * 0.002
  })

  const activeIndex = pinned ?? hovered
  const hoverPoint = activeIndex === null ? null : visiblePoints[activeIndex]
  return (
    <group>
      <instancedMesh ref={ref} args={[undefined, undefined, visiblePoints.length]}>
        <cylinderGeometry args={[0.035, 0.07, 1, quality === 'LOW' ? 5 : 8]} />
        <meshStandardMaterial roughness={0.32} metalness={0.28} emissiveIntensity={0.25} />
      </instancedMesh>
      {/* Invisible, wider twin of the bar above: the real hover/click target. A human hand
          can't hold a cursor perfectly still, and the visible bar is only ~0.035-0.07 world
          units wide - on a map with hundreds of them that's a couple of screen pixels, well
          inside normal mouse jitter. Raycasting against that thin geometry directly made the
          panel flicker shut mid-hover as jitter drifted off it every so often; picking against
          this padded proxy instead (same transform, roughly double the radius, fully transparent)
          gives jitter somewhere to land without changing how thin the bars themselves look. */}
      <instancedMesh
        ref={hitRef}
        args={[undefined, undefined, visiblePoints.length]}
        onPointerMove={(event) => {
          event.stopPropagation()
          clearHideTimer()
          setHovered(event.instanceId ?? null)
          document.body.style.cursor = 'pointer'
        }}
        onPointerOut={() => {
          scheduleHide()
          document.body.style.cursor = ''
        }}
        onClick={(event) => {
          event.stopPropagation()
          if (event.instanceId !== undefined) onSelect(visiblePoints[event.instanceId])
        }}
      >
        <cylinderGeometry args={[0.08, 0.14, 1, quality === 'LOW' ? 5 : 8]} />
        <meshBasicMaterial transparent opacity={0} depthWrite={false} />
      </instancedMesh>
      {hoverPoint && (
        <Html position={projectWorld(hoverPoint.lon, hoverPoint.lat)} center distanceFactor={10} zIndexRange={[20, 0]}>
          {/* First hover shows this panel; clicking anywhere on it pins it open for 10s so the
              follow-up click on "Inspeksi" below has a reliable window to land, instead of
              racing the cursor leaving the tiny point mesh underneath. */}
          <div className="spatial-tooltip" onMouseEnter={clearHideTimer} onClick={() => pin(activeIndex as number)}>
            <strong>{hoverPoint.unit}</strong>
            <span>{hoverPoint.location}</span>
            <b>{hoverPoint.readiness === null ? '—' : `${hoverPoint.readiness.toFixed(1)}%`}</b>
            <button
              type="button"
              className="tooltip-inspect"
              onClick={(event) => { event.stopPropagation(); clearPinTimer(); setPinned(null); onSelect(hoverPoint) }}
            >
              <Crosshair size={11} /> Inspeksi
            </button>
          </div>
        </Html>
      )}
    </group>
  )
}

export function RiskZones({ clusters }: { clusters: Cluster[] }) {
  const [hovered, setHovered] = useState<string | null>(null)

  useEffect(() => {
    document.body.style.cursor = hovered ? 'pointer' : ''
    return () => { document.body.style.cursor = '' }
  }, [hovered])

  return (
    <group>
      {clusters.slice(0, 24).map((cluster) => {
        const isHovered = hovered === cluster.cluster_id
        const color = cluster.severity === 'CRITICAL' ? '#9b3d36' : cluster.severity === 'HIGH' ? '#a77b45' : '#54756c'
        const polygon = cluster.coordinates.map(([lat, lon]) => {
          const [x, , z] = projectWorld(lon, lat)
          return [x, 0.26, z] as [number, number, number]
        })
        if (polygon.length > 2) polygon.push(polygon[0])
        const center = projectWorld(cluster.centroid.lon, cluster.centroid.lat)
        const outerRadius = 0.19 + Math.min(0.28, cluster.member_count / 120)
        return (
          <group
            key={cluster.cluster_id}
            onPointerOver={(event) => { event.stopPropagation(); setHovered(cluster.cluster_id) }}
            onPointerOut={(event) => { event.stopPropagation(); setHovered(null) }}
          >
            {polygon.length > 1 && <Line points={polygon} color={color} lineWidth={isHovered ? 2.3 : 1.3} transparent opacity={isHovered ? 1 : 0.8} />}
            <mesh position={[center[0], 0.29, center[2]]} rotation={[Math.PI / 2, 0, 0]} scale={isHovered ? 1.12 : 1}>
              <ringGeometry args={[0.12, outerRadius, 40]} />
              <meshBasicMaterial color={color} transparent opacity={isHovered ? 0.82 : 0.52} side={THREE.DoubleSide} />
            </mesh>
            <mesh position={[center[0], 0.3, center[2]]} rotation={[Math.PI / 2, 0, 0]}>
              <circleGeometry args={[Math.max(outerRadius, 0.3), 32]} />
              <meshBasicMaterial transparent opacity={0.001} depthWrite={false} side={THREE.DoubleSide} />
            </mesh>
            {isHovered && (
              <Html position={[center[0], 1.05, center[2]]} center distanceFactor={9} zIndexRange={[30, 0]}>
                <div className="spatial-tooltip cluster-tooltip">
                  <span className={`tooltip-severity ${cluster.severity.toLowerCase()}`}>{cluster.severity}</span>
                  <strong>{cluster.cluster_id}</strong>
                  <span>{cluster.locations.join(', ')}</span>
                  <b>{cluster.member_count} anggota · {cluster.unit_count} unit</b>
                  <small>Kesiapan rata-rata {cluster.average_readiness === null ? '—' : `${cluster.average_readiness.toFixed(1)}%`}</small>
                </div>
              </Html>
            )}
          </group>
        )
      })}
    </group>
  )
}

export function PredictiveConstellation({ risks }: { risks: RiskItem[] }) {
  const [hovered, setHovered] = useState<string | null>(null)

  useEffect(() => {
    document.body.style.cursor = hovered ? 'pointer' : ''
    return () => { document.body.style.cursor = '' }
  }, [hovered])

  return (
    <group>
      {risks.slice(0, 15).map((risk, index) => {
        if (risk.lat === null || risk.lon === null) return null
        const angle = index * 2.399
        const anchor = projectWorld(risk.lon, risk.lat)
        const orb: [number, number, number] = [
          anchor[0] + Math.cos(angle) * (0.32 + (index % 3) * 0.06),
          1.15 + (risk.hidden_risk / 100) * 1.05 + (index % 3) * 0.12,
          anchor[2] + Math.sin(angle) * (0.32 + (index % 2) * 0.08),
        ]
        const color = risk.is_anomaly ? '#9b3d36' : '#a77b45'
        const isHovered = hovered === risk.id
        return (
          <group key={risk.id}>
            <Line points={[anchor, orb]} color={color} lineWidth={isHovered ? 1.35 : 0.65} dashed dashSize={0.06} gapSize={0.045} transparent opacity={isHovered ? 0.95 : 0.46} />
            <mesh position={[anchor[0], 0.25, anchor[2]]} rotation={[Math.PI / 2, 0, 0]}>
              <ringGeometry args={[0.035, isHovered ? 0.12 : 0.08, 24]} />
              <meshBasicMaterial color={color} transparent opacity={isHovered ? 0.95 : 0.58} side={THREE.DoubleSide} />
            </mesh>
            <mesh
              position={orb}
              scale={isHovered ? 1.35 : 1}
              onPointerOver={(event) => { event.stopPropagation(); setHovered(risk.id) }}
              onPointerOut={(event) => { event.stopPropagation(); setHovered(null) }}
            >
              <sphereGeometry args={[0.075 + risk.hidden_risk * 0.00065, 18, 18]} />
              <meshStandardMaterial color={color} emissive={color} emissiveIntensity={isHovered ? 1.15 : 0.65} roughness={0.28} />
            </mesh>
            {isHovered && (
              <Html position={[orb[0], orb[1] + 0.34, orb[2]]} center distanceFactor={9} zIndexRange={[32, 0]}>
                <div className="spatial-tooltip predictive-tooltip">
                  <span className="tooltip-kicker">Unit berisiko</span>
                  <strong>{risk.unit}</strong>
                  <span>{risk.location} · {risk.category}</span>
                  <b>Risiko tersembunyi {risk.hidden_risk.toFixed(2)}</b>
                  <small>Kesiapan {risk.readiness.toFixed(1)}% · {risk.status}</small>
                </div>
              </Html>
            )}
          </group>
        )
      })}
    </group>
  )
}
