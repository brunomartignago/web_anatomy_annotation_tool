import type { PageAnnotationFileV1 } from './annotation'
import type { PageResponse, PageSummary, ProjectsResponse, SaveResponse, Taxonomy } from './types'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function getJson<T>(path: string): Promise<T> {
  return requestJson<T>(path, { headers: { Accept: 'application/json' } })
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(path, init)
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
  page: (project: string, pageId: string) =>
    getJson<PageResponse>(`/api/pages/${encodeURIComponent(pageId)}${projectQuery(project)}`),
  /** Replace annotations.json. `etag` must be the one from the last load or save: if the
   *  file changed since, the server answers 412 and nothing is overwritten. */
  save: (project: string, pageId: string, doc: PageAnnotationFileV1, etag: string) =>
    requestJson<SaveResponse>(
      `/api/pages/${encodeURIComponent(pageId)}/annotations${projectQuery(project)}`,
      {
        method: 'PUT',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          'If-Match': etag,
        },
        body: JSON.stringify(doc),
      },
    ),
}

/** URL of one 2048-px WebP strip of a page's screenshot. */
export function stripUrl(project: string, pageId: string, n: number): string {
  return `/api/pages/${encodeURIComponent(pageId)}/strips/${n}.webp${projectQuery(project)}`
}

function projectQuery(project: string): string {
  return `?project=${encodeURIComponent(project)}`
}
