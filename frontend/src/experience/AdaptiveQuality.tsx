import { useFrame, useThree } from '@react-three/fiber'
import { useRef } from 'react'
import { useSatriaStore } from '../store/useSatriaStore'
import type { EffectiveQuality } from '../types'

const LEVELS: EffectiveQuality[] = ['LOW', 'MEDIUM', 'HIGH', 'ULTRA']
const DPR: Record<EffectiveQuality, number> = { LOW: 0.85, MEDIUM: 1.15, HIGH: 1.5, ULTRA: 2 }

export function AdaptiveQuality() {
  const preset = useSatriaStore((state) => state.graphicsPreset)
  const effective = useSatriaStore((state) => state.effectiveQuality)
  const setEffective = useSatriaStore((state) => state.setEffectiveQuality)
  const setFps = useSatriaStore((state) => state.setFps)
  const setRendererStats = useSatriaStore((state) => state.setRendererStats)
  const setDpr = useThree((state) => state.setDpr)
  const elapsed = useRef(0)
  const frames = useRef(0)
  const lastAdjustment = useRef(0)
  const strongWindows = useRef(0)

  useFrame((state, delta) => {
    elapsed.current += delta
    frames.current += 1
    if (elapsed.current < 2) return

    const fps = frames.current / elapsed.current
    setFps(Math.round(fps))
    const memory = (performance as Performance & { memory?: { usedJSHeapSize: number } }).memory
    setRendererStats({
      drawCalls: state.gl.info.render.calls,
      triangles: state.gl.info.render.triangles,
      geometries: state.gl.info.memory.geometries,
      textures: state.gl.info.memory.textures,
      heapMb: memory ? Math.round(memory.usedJSHeapSize / 1024 / 1024) : null,
    })
    setDpr(Math.min(window.devicePixelRatio || 1, DPR[effective]))
    const now = state.clock.elapsedTime

    if (preset === 'AUTO' && now - lastAdjustment.current > 8) {
      const currentIndex = LEVELS.indexOf(effective)
      const floor = effective === 'LOW' ? 27 : effective === 'MEDIUM' ? 38 : 48
      if (fps < floor && currentIndex > 0) {
        setEffective(LEVELS[currentIndex - 1])
        lastAdjustment.current = now
        strongWindows.current = 0
      } else if (fps > 58 && currentIndex < LEVELS.length - 1) {
        strongWindows.current += 1
        if (strongWindows.current >= 4) {
          setEffective(LEVELS[currentIndex + 1])
          lastAdjustment.current = now
          strongWindows.current = 0
        }
      } else {
        strongWindows.current = 0
      }
    } else if (preset !== 'AUTO' && preset !== effective) {
      setEffective(preset)
      lastAdjustment.current = now
    }

    elapsed.current = 0
    frames.current = 0
  })
  return null
}
