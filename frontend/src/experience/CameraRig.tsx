import { useFrame } from '@react-three/fiber'
import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import type { Zone } from '../types'

const CAMERA_POSITIONS: Record<Zone, [number, number, number]> = {
  command: [0.2, 4.1, 13.2],
  map: [3.8, 5.8, 10.5],
  readiness: [-3.4, 4.2, 11.5],
  spatial: [4.9, 6.3, 9.8],
  predictive: [-4.4, 5.3, 10.4],
  diagnostics: [0, 7.2, 14.8],
  data: [1.2, 5.8, 15.5],
  ai: [-1.8, 3.5, 9.2],
  system: [0.2, 6.2, 16.8],
}

const CAMERA_TARGETS: Record<Zone, [number, number, number]> = {
  command: [0, 0.1, 0],
  map: [2.9, -0.4, 0],
  readiness: [-1.1, 0.2, 0],
  spatial: [3.2, -0.2, 0],
  predictive: [-1.6, 0.4, 0],
  diagnostics: [0, -0.3, 0],
  data: [1, -0.2, 0],
  ai: [-0.8, 0.8, 0],
  system: [0, 0, 0],
}

export function CameraRig({ zone, zoom = 1 }: { zone: Zone; zoom?: number }) {
  const reducedMotion = useRef(false)
  const target = useRef(new THREE.Vector3())
  const destination = useRef(new THREE.Vector3())
  const desiredTarget = useRef(new THREE.Vector3())
  const basePosition = useRef(new THREE.Vector3())

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => (reducedMotion.current = media.matches)
    update()
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])

  useFrame((state, delta) => {
    desiredTarget.current.set(...CAMERA_TARGETS[zone])
    basePosition.current.set(...CAMERA_POSITIONS[zone])
    // Zoom pulls the camera along the target->camera line rather than just changing FOV, so
    // points near screen edges stay put under the pointer instead of the whole view warping.
    destination.current.copy(basePosition.current).sub(desiredTarget.current).multiplyScalar(zoom).add(desiredTarget.current)
    if (!reducedMotion.current) {
      destination.current.x += state.pointer.x * 0.18
      destination.current.y += state.pointer.y * 0.1
    }
    const damping = reducedMotion.current ? 12 : 2.3
    state.camera.position.lerp(destination.current, 1 - Math.exp(-damping * delta))
    target.current.lerp(desiredTarget.current, 1 - Math.exp(-3 * delta))
    state.camera.lookAt(target.current)
  })
  return null
}
