import { useEffect } from 'react'

import { api } from './api/client'
import type { PageSummary } from './api/types'
import { useAppStore } from './state/store'

// The shell: loads the served project and lists its pages. The canvas (2.3), tools (2.4)
// and panels (2.5) plug in here.
export default function App() {
  const { status, error, taxonomy, project, pages, currentPageId } = useAppStore()
  const { startLoading, loaded, failed, openPage } = useAppStore()

  useEffect(() => {
    let cancelled = false
    startLoading()
    ;(async () => {
      try {
        const [tax, projects] = await Promise.all([api.taxonomy(), api.projects()])
        const list = await api.pages(projects.current)
        if (!cancelled) loaded(tax, projects.current, list)
      } catch (exc) {
        if (!cancelled) failed(exc instanceof Error ? exc.message : String(exc))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [startLoading, loaded, failed])

  return (
    <div className="app">
      <header className="app__header">
        <h1>annotool</h1>
        {project && <span className="app__project">{project}</span>}
        {taxonomy && (
          <span className="app__taxonomy">
            {taxonomy.name} v{taxonomy.version}
          </span>
        )}
      </header>

      <main className="app__main">
        {status === 'loading' && <p role="status">Loading…</p>}
        {status === 'error' && (
          <p role="alert" className="app__error">
            Couldn't reach the annotool server: {error}. Start it with{' '}
            <code>uv run annotool serve --project &lt;name&gt;</code>.
          </p>
        )}
        {status === 'ready' && (
          <PageList pages={pages} currentPageId={currentPageId} onOpen={openPage} />
        )}
      </main>
    </div>
  )
}

function PageList(props: {
  pages: PageSummary[]
  currentPageId: string | null
  onOpen: (id: string) => void
}) {
  if (props.pages.length === 0) {
    return <p>This project has no pages yet. Capture some with <code>annotool capture</code>.</p>
  }
  return (
    <ul className="pages" aria-label="Pages">
      {props.pages.map((page) => {
        const { boxes, complete } = page.progress
        return (
          <li key={page.id}>
            <button
              type="button"
              className="pages__item"
              aria-current={page.id === props.currentPageId ? 'true' : undefined}
              onClick={() => props.onOpen(page.id)}
            >
              <span className="pages__id">{page.id}</span>
              <span className="pages__progress">
                {page.blocked ? 'blocked' : `${complete}/${boxes} boxes complete`}
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
