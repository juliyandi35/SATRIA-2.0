import { Float, Html, Icosahedron, MeshTransmissionMaterial, Torus } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { useSatriaStore } from '../store/useSatriaStore'
import type { AiActivity, EffectiveQuality, Zone } from '../types'

function readinessColor(readiness: number | null) {
  if (readiness === null) return '#8b9a92'
  if (readiness < 60) return '#9b3d36'
  if (readiness < 80) return '#a77b45'
  return '#17666a'
}

const NAV_ZONES: Array<{ id: Zone; label: string }> = [
  { id: 'command', label: 'Command Nexus' },
  { id: 'map', label: 'Peta Nusantara' },
  { id: 'readiness', label: 'Kesiapan' },
  { id: 'spatial', label: 'Risiko spasial' },
  { id: 'predictive', label: 'Risiko tersembunyi' },
  { id: 'diagnostics', label: 'Diagnostik' },
  { id: 'data', label: 'Data' },
  { id: 'ai', label: 'SATRIA AI' },
  { id: 'system', label: 'Sistem' },
]

function ZoneConstellation({ zone }: { zone: Zone }) {
  const setZone = useSatriaStore((state) => state.setZone)
  const ring = useRef<THREE.Group>(null)
  const [hovered, setHovered] = useState<Zone | null>(null)

  useFrame((_, delta) => {
    if (ring.current) ring.current.rotation.y += delta * 0.05
  })

  return (
    <group ref={ring}>
      {NAV_ZONES.map((entry, index) => {
        const angle = (index / NAV_ZONES.length) * Math.PI * 2
        const radius = 2.35
        const position: [number, number, number] = [Math.cos(angle) * radius, Math.sin(angle * 2) * 0.28, Math.sin(angle) * radius * 0.82]
        const isActive = zone === entry.id
        const isHovered = hovered === entry.id
        const color = isActive ? '#f2ede0' : isHovered ? '#7fb8b0' : '#5c766e'
        return (
          <group key={entry.id} position={position}>
            <mesh
              scale={isActive ? 1.4 : isHovered ? 1.25 : 1}
              onPointerOver={(event) => { event.stopPropagation(); setHovered(entry.id); document.body.style.cursor = 'pointer' }}
              onPointerOut={(event) => { event.stopPropagation(); setHovered(null); document.body.style.cursor = '' }}
              onClick={(event) => { event.stopPropagation(); setZone(entry.id) }}
            >
              <sphereGeometry args={[0.055, 16, 16]} />
              <meshStandardMaterial color={color} emissive={color} emissiveIntensity={isActive ? 1.4 : 0.6} roughness={0.3} />
            </mesh>
            {isHovered && (
              <Html center distanceFactor={9} position={[0, 0.22, 0]} zIndexRange={[25, 0]}>
                <div className="spatial-tooltip"><strong>{entry.label}</strong></div>
              </Html>
            )}
          </group>
        )
      })}
    </group>
  )
}

export function IntelligenceCore({
  loaded,
  readiness,
  quality,
  activity,
  zone,
}: {
  loaded: boolean
  readiness: number | null
  quality: EffectiveQuality
  activity: AiActivity
  zone: Zone
}) {
  const group = useRef<THREE.Group>(null)
  const inner = useRef<THREE.Mesh>(null)
  const setZone = useSatriaStore((state) => state.setZone)
  const [coreHovered, setCoreHovered] = useState(false)
  const color = useMemo(() => readinessColor(readiness), [readiness])
  const detail = quality === 'LOW' ? 1 : quality === 'MEDIUM' ? 2 : 3

  useFrame((state, delta) => {
    if (group.current) group.current.rotation.y += delta * (activity === 'thinking' ? 0.35 : 0.08)
    if (inner.current) {
      const base = (activity === 'thinking' ? 1.13 : activity === 'answering' ? 1.07 : 1) * (coreHovered ? 1.06 : 1)
      const pulse = loaded ? Math.sin(state.clock.elapsedTime * (activity === 'thinking' ? 4 : 1.3)) * 0.025 : 0
      inner.current.scale.setScalar(base + pulse)
    }
  })

  const position: [number, number, number] = !loaded
    ? [1.15, 0.45, 0]
    : zone === 'spatial'
      ? [-3.55, 1.55, -1.35]
      : [-4.65, 1.55, -1.35]
  const scale = loaded ? (zone === 'spatial' ? 0.58 : 0.72) : 1

  return (
    <group ref={group} position={position} scale={scale}>
      <Float speed={loaded ? 1.1 : 0.45} rotationIntensity={0.08} floatIntensity={0.22}>
        {loaded && (
          <Icosahedron args={[1.34, detail]} scale={coreHovered ? 1.06 : 1}>
            <meshBasicMaterial color={color} transparent opacity={0.22} side={THREE.BackSide} blending={THREE.AdditiveBlending} depthWrite={false} />
          </Icosahedron>
        )}
        <Icosahedron
          ref={inner}
          args={[1.2, detail]}
          onPointerOver={(event) => { if (!loaded) return; event.stopPropagation(); setCoreHovered(true); document.body.style.cursor = 'pointer' }}
          onPointerOut={(event) => { if (!loaded) return; event.stopPropagation(); setCoreHovered(false); document.body.style.cursor = '' }}
          onClick={(event) => { if (!loaded) return; event.stopPropagation(); setZone('ai') }}
        >
          {quality === 'LOW' ? (
            <meshPhysicalMaterial color={loaded ? color : '#88a198'} roughness={0.34} metalness={0.1} transparent opacity={0.78} />
          ) : (
            <MeshTransmissionMaterial
              color={loaded ? color : '#88a198'}
              transmission={loaded ? 0.76 : 0.6}
              thickness={0.85}
              roughness={0.18}
              metalness={0.05}
              chromaticAberration={quality === 'ULTRA' ? 0.018 : 0.005}
              anisotropy={0.18}
              distortion={loaded ? 0.16 : 0.04}
              distortionScale={0.22}
              temporalDistortion={loaded ? 0.08 : 0}
            />
          )}
        </Icosahedron>
        <Icosahedron args={[0.62, 2]}>
          <meshStandardMaterial color={loaded ? color : '#54756c'} emissive={loaded ? color : '#54756c'} emissiveIntensity={loaded ? 1.3 : 0.48} roughness={0.28} />
        </Icosahedron>
      </Float>
      {(quality === 'LOW' ? [1.65] : [1.65, 2.02, 2.46]).map((radius, index) => (
        <Torus key={radius} args={[radius, index === 0 ? 0.025 : 0.014, 8, 160]} rotation={[Math.PI / 2 + index * 0.35, 0.25 * index, 0.2]}>
          <meshStandardMaterial color={index === 0 ? '#a77b45' : '#6d857c'} metalness={0.72} roughness={0.32} transparent opacity={loaded ? 0.68 - index * 0.12 : 0.42 - index * 0.07} />
        </Torus>
      ))}
      {loaded && quality !== 'LOW' && <ZoneConstellation zone={zone} />}
      <pointLight color={loaded ? color : '#d7e1de'} intensity={loaded ? 18 : 4} distance={8} decay={2} />
    </group>
  )
}
