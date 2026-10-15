// Shapes of the server's responses (backend/src/annotool/server/routes.py and store.py).
// The annotation file itself is generated from the JSON Schema: see ./annotation.ts.

import type { PageAnnotationFileV1 } from './annotation'

export interface TaxonomyOption {
  value: string
  key: string
  status: 'active' | 'proposed'
  note?: string | null
}

export interface TaxonomyAttribute {
  id: string
  label: string
  hotkey: string
  question?: string | null
  options: TaxonomyOption[]
  inherit_from_parent: boolean
  computed_by_rules: boolean
}

export interface Preset {
  key: string
  labels: Record<string, string>
}

export interface Taxonomy {
  id: string
  version: string
  name: string
  description?: string | null
  attributes: TaxonomyAttribute[]
  presets: Preset[]
  rules: Record<string, unknown>
}

export interface ProjectSummary {
  name: string
  pages: number
}

export interface ProjectsResponse {
  current: string
  projects: ProjectSummary[]
}

export interface Progress {
  boxes: number
  empty: number
  partial: number
  complete: number
  suggested: number
  labeled: Record<string, number>
}

export interface PageSummary {
  id: string
  url?: string | null
  title?: string | null
  category?: string | null
  page_type?: string | null
  width?: number | null
  height?: number | null
  blocked: boolean
  blocked_reasons: string[]
  has_annotations: boolean
  has_image: boolean
  has_dom: boolean
  strips: number
  progress: Progress
  error?: string | null
}

export interface SaveResponse {
  etag: string
  progress: Progress
}

export interface PageResponse {
  project: string
  etag: string
  annotations: PageAnnotationFileV1
  meta?: Record<string, unknown> | null
  has_dom: boolean
  strips: { height: number; count: number }
}
