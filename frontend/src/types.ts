export type Zone = 'command' | 'map' | 'readiness' | 'spatial' | 'predictive' | 'diagnostics' | 'data' | 'ai' | 'system'
export type GraphicsPreset = 'AUTO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'ULTRA'
export type EffectiveQuality = Exclude<GraphicsPreset, 'AUTO'>
export type AiActivity = 'idle' | 'thinking' | 'answering' | 'error'
export type SpatialVisualMode = 'points' | 'clusters' | 'combined'

export interface Filters {
  location?: string
  unit?: string
  satuan?: string
  category?: string
  status?: string
  risk?: string
  readiness_min?: number
  readiness_max?: number
}

export interface Summary {
  record_count: number
  unit_count: number
  province_count: number
  average_readiness: number | null
  median_readiness: number | null
  flagged_count: number
  attention_count: number
  minimum_readiness: number | null
  maximum_readiness: number | null
  latest_sync: string | null
}

export interface MapPoint {
  unit: string
  location: string
  lat: number
  lon: number
  readiness: number | null
  record_count: number
  flagged_count: number
  categories: string[]
}

export interface RecordRow {
  id: string
  category: string
  unit: string
  location: string
  lat: number | null
  lon: number | null
  readiness: number | null
  status: string
  last_sync: string | null
  source_index: number
}

export interface DistributionItem {
  name: string
  count: number
  average_readiness?: number | null
}

export interface RankingItem {
  unit: string
  location: string
  readiness: number | null
  records: number
  flagged: number
}

export interface DataView {
  summary: Summary
  distributions: {
    category: DistributionItem[]
    status: DistributionItem[]
    province: DistributionItem[]
    readiness: DistributionItem[]
  }
  rankings: {
    lowest_units: RankingItem[]
    highest_units: RankingItem[]
    provinces: Array<{ location: string; readiness: number | null; records: number }>
  }
  map_points: MapPoint[]
  records: RecordRow[]
  pagination: { page: number; page_size: number; total_records: number; total_pages: number }
  filter_options: Record<'location' | 'unit' | 'satuan' | 'category' | 'status', string[]>
  quality: Record<string, unknown>
  active_filters: Filters
}

export interface Cluster {
  cluster_id: string
  severity: 'CRITICAL' | 'HIGH' | 'WATCH'
  coordinates: [number, number][]
  centroid: { lat: number; lon: number }
  member_count: number
  unit_count: number
  average_readiness: number | null
  flagged_count: number
  locations: string[]
}

export interface SpatialResult {
  method: string
  risk_point_count: number
  noise_count: number
  clusters: Cluster[]
  parameters: { epsilon_km: number; min_samples: number }
}

export interface RiskItem {
  id: string
  unit: string
  location: string
  category: string
  hidden_risk: number
  readiness: number
  status: string
  is_anomaly: boolean
  lat: number | null
  lon: number | null
}

export interface PredictiveResult {
  method: string
  confidence: number
  confidence_method: string
  peak_risk: number
  anomaly_count: number
  excluded_count: number
  features_analyzed: string[]
  top_risks: RiskItem[]
}

export interface ActualRecord {
  unit_node: string
  unit_type: string
  location: string
  lat: number
  lon: number
  personnel: number
  equipment: number
  logistics: number
  infrastructure: number
  training: number
}

export interface ReferenceRecord {
  unit_type: string
  personnel: number
  equipment: number
  logistics: number
  infrastructure: number
  training: number
}

export interface ModelStatus {
  name: string
  provider: string
  available: boolean
  resolved_name: string | null
  ollama_online: boolean
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
}
