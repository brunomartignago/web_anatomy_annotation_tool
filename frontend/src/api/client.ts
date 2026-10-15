import type { PageSummary, ProjectsResponse, Taxonomy } from './types'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: 'application/json' } })
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // not JSON; keep the status text
    }
    throw new ApiError(response.status, `${path}: ${response.status} ${detail}`)
  }
  return (await response.json()) as T
}

export const api = {
  taxonomy: () => getJson<Taxonomy>('/api/taxonomy'),
  projects: () => getJson<ProjectsResponse>('/api/projects'),
  pages: (project: string) =>
    getJson<PageSummary[]>(`/api/projects/${encodeURIComponent(project)}/pages`),
}
