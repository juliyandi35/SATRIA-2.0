import { create } from 'zustand'
import type {
  AiActivity,
  ChatMessage,
  DataView,
  EffectiveQuality,
  Filters,
  GraphicsPreset,
  ModelStatus,
  PredictiveResult,
  SpatialResult,
  SpatialVisualMode,
  Zone,
} from '../types'

interface SatriaState {
  zone: Zone
  loaded: boolean
  importing: boolean
  metadata: Record<string, unknown> | null
  view: DataView | null
  filters: Filters
  spatial: SpatialResult | null
  spatialVisualMode: SpatialVisualMode
  predictive: PredictiveResult | null
  diagnostics: Record<string, any> | null
  system: Record<string, any> | null
  models: ModelStatus[]
  selectedModel: string
  graphicsPreset: GraphicsPreset
  effectiveQuality: EffectiveQuality
  fps: number
  rendererStats: { drawCalls: number; triangles: number; geometries: number; textures: number; heapMb: number | null }
  aiActivity: AiActivity
  localOnly: boolean
  auditLog: boolean
  chatMessages: ChatMessage[]
  chatSessionId: string
  setZone: (zone: Zone) => void
  setLoaded: (loaded: boolean) => void
  setImporting: (importing: boolean) => void
  setMetadata: (metadata: Record<string, unknown> | null) => void
  setView: (view: DataView | null) => void
  setFilters: (filters: Filters) => void
  setSpatial: (spatial: SpatialResult | null) => void
  setSpatialVisualMode: (spatialVisualMode: SpatialVisualMode) => void
  setPredictive: (predictive: PredictiveResult | null) => void
  setDiagnostics: (diagnostics: Record<string, any> | null) => void
  setSystem: (system: Record<string, any> | null) => void
  setModels: (models: ModelStatus[]) => void
  setSelectedModel: (selectedModel: string) => void
  setGraphicsPreset: (graphicsPreset: GraphicsPreset) => void
  setEffectiveQuality: (effectiveQuality: EffectiveQuality) => void
  setFps: (fps: number) => void
  setRendererStats: (rendererStats: SatriaState['rendererStats']) => void
  setAiActivity: (aiActivity: AiActivity) => void
  setLocalOnly: (localOnly: boolean) => void
  setAuditLog: (auditLog: boolean) => void
  appendChatMessage: (message: ChatMessage) => void
  clearChatMessages: () => void
}

export const useSatriaStore = create<SatriaState>((set) => ({
  zone: 'command',
  loaded: false,
  importing: false,
  metadata: null,
  view: null,
  filters: {},
  spatial: null,
  spatialVisualMode: 'combined',
  predictive: null,
  diagnostics: null,
  system: null,
  models: [],
  selectedModel: 'granite4.2:3b',
  graphicsPreset: 'AUTO',
  effectiveQuality: 'HIGH',
  fps: 0,
  rendererStats: { drawCalls: 0, triangles: 0, geometries: 0, textures: 0, heapMb: null },
  aiActivity: 'idle',
  localOnly: true,
  auditLog: false,
  chatMessages: [],
  chatSessionId: `satria-${crypto.randomUUID()}`,
  setZone: (zone) => set({ zone }),
  setLoaded: (loaded) => set({ loaded }),
  setImporting: (importing) => set({ importing }),
  setMetadata: (metadata) => set({ metadata }),
  setView: (view) => set({ view }),
  setFilters: (filters) => set({ filters }),
  setSpatial: (spatial) => set({ spatial }),
  setSpatialVisualMode: (spatialVisualMode) => set({ spatialVisualMode }),
  setPredictive: (predictive) => set({ predictive }),
  setDiagnostics: (diagnostics) => set({ diagnostics }),
  setSystem: (system) => set({ system }),
  setModels: (models) => set({ models }),
  setSelectedModel: (selectedModel) => set({ selectedModel }),
  setGraphicsPreset: (graphicsPreset) => set({ graphicsPreset }),
  setEffectiveQuality: (effectiveQuality) => set({ effectiveQuality }),
  setFps: (fps) => set({ fps }),
  setRendererStats: (rendererStats) => set({ rendererStats }),
  setAiActivity: (aiActivity) => set({ aiActivity }),
  setLocalOnly: (localOnly) => set({ localOnly }),
  setAuditLog: (auditLog) => set({ auditLog }),
  appendChatMessage: (message) => set((state) => ({ chatMessages: [...state.chatMessages, message] })),
  clearChatMessages: () => set({ chatMessages: [] }),
}))
