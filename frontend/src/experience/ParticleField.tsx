import { Points, PointMaterial } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import type { EffectiveQuality } from '../types'

export function ParticleField({ quality }: { quality: EffectiveQuality }) {
  const ref = useRef<THREE.Points>(null)
  const count = quality === 'LOW' ? 60 : quality === 'MEDIUM' ? 360 : quality === 'HIGH' ? 780 : 1300
  const points = useMemo(() => {
    const array = new Float32Array(count * 3)
    for (let index = 0; index < count; index++) {
      const spiral = index * 2.399963
      const radius = 4 + ((index * 37) % 100) / 12
      array[index * 3] = Math.cos(spiral) * radius
      array[index * 3 + 1] = ((index * 53) % 100) / 16 - 2.8
      array[index * 3 + 2] = Math.sin(spiral) * radius
    }
    return array
  }, [count])

  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.006
  })
  return (
    <Points ref={ref} positions={points} stride={3} frustumCulled>
      <PointMaterial color="#69827a" size={quality === 'ULTRA' ? 0.026 : 0.02} transparent opacity={0.28} sizeAttenuation depthWrite={false} />
    </Points>
  )
}
