import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Annotation } from '../api/annotation'
import type { PageResponse, SuggestReport } from '../api/types'
import { initialState, useAppStore } from '../state/store'
import { runSuggest, summarizeReports } from './suggest'

const store = () => useAppStore.getState()
const progress = { boxes: 1, empty: 0, partial: 1, complete: 0, suggested: 1, labeled: {} }

const HUMAN: Annotation = {
  id: 'a',
  kind: 'element',
  bbox: [0, 0, 100, 50],
  labels: { Form: 'Typo' },
  source: 'human',
  status: 'accepted',
}
const SUGGESTED: Annotation = {
  id: 'new',
  kind: 'element',
  bbox: [0, 100, 300, 40],
  labels: { Function: 'Heading' },
  source: 'dom',
  status: 'suggested',
  label_sources: { Function: 'dom' },
}

const PAGE: PageResponse = {
  project: 'demo',
  etag: '"v1"',
  has_dom: true,
  strips: { height: 2048, count: 1 },
  annotations: {
    schema_version: '1.0',
    taxonomy: { id: 'web-ui', version: '1.0' },
    page: { id: 'p', image: 'page.png', width: 1920, height: 2000 },
    annotations: [HUMAN],
  },
}

const report = (extra: Partial<SuggestReport> = {}): SuggestReport => ({
  suggester: 'dom',
  boxes_added: 1,
  boxes_matched: 0,
  labels_set: 1,
  kept_human: 0,
  kept_better: 0,
  skipped_rejected: 0,
  dropped: [],
  error: null,
  changed: true,
  ...extra,
})

type Reply = { status: number; body: unknown }
const calls: { url: string; init?: RequestInit }[] = []

function mockServer(...replies: Reply[]) {
  calls.length = 0
  let n = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init })
      const reply = replies[Math.min(n++, replies.length - 1)]
      return new Response(JSON.stringify(reply.body), { status: reply.status })
    }),
  )
}

const suggested = (etag: string): Reply => ({
  status: 200,
  body: {
    etag,
    annotations: { ...PAGE.annotations, annotations: [HUMAN, SUGGESTED] },
    reports: [report()],
    progress,
  },
})

describe('Suggest (4.1)', () => {
  beforeEach(() => {
    useAppStore.setState({ ...initialState, project: 'demo', suggesters: ['dom'] })
    store().pageLoaded('p', PAGE)
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('applies the suggestions as one undo step, with the new ETag', async () => {
    mockServer(suggested('"v2"'))
    await runSuggest()
    expect(calls[0].url).toBe('/api/pages/p/suggest?project=demo')
    expect(calls[0].init?.method).toBe('POST')
    expect((calls[0].init?.headers as Record<string, string>)['If-Match']).toBe('"v1"')
    expect(store().page!.annotations.annotations.map((b) => b.id)).toEqual(['a', 'new'])
    expect(store().page!.etag).toBe('"v2"')
    expect(store().notice).toBe('Suggestions: +1 box, 1 label (dom)')
    expect(store().suggesting).toBe(false)

    store().undo() // takes the suggestions back
    expect(store().page!.annotations.annotations.map((b) => b.id)).toEqual(['a'])
  })

  it('saves unsaved edits first, then suggests on the saved version', async () => {
    mockServer({ status: 200, body: { etag: '"v1b"', progress } }, suggested('"v2"'))
    store().addBox([500, 500, 50, 50])
    await runSuggest()
    expect(calls.map((c) => c.init?.method)).toEqual(['PUT', 'POST'])
    expect((calls[1].init?.headers as Record<string, string>)['If-Match']).toBe('"v1b"')
  })

  it('a file changed elsewhere stops it with the conflict warning', async () => {
    mockServer({ status: 412, body: { detail: 'changed', etag: '"x"' } })
    await runSuggest()
    expect(store().saveState).toBe('conflict')
    expect(store().page!.annotations.annotations).toHaveLength(1)
  })

  it('edits made while the suggesters ran are not silently replaced', async () => {
    let release: (value: Response) => void = () => {}
    const fetchMock = vi.fn(() => new Promise<Response>((resolve) => (release = resolve)))
    vi.stubGlobal('fetch', fetchMock)
    const running = runSuggest()
    expect(store().suggesting).toBe(true)
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1)) // the POST is out
    store().addBox([500, 500, 50, 50]) // edited during the request
    release(new Response(JSON.stringify(suggested('"v2"').body), { status: 200 }))
    await running
    expect(store().saveState).toBe('conflict')
    expect(store().page!.annotations.annotations.map((b) => b.id)).not.toContain('new')
  })

  it('does nothing without suggesters', async () => {
    useAppStore.setState({ suggesters: [] })
    mockServer(suggested('"v2"'))
    await runSuggest()
    expect(calls).toHaveLength(0)
  })
})

describe('summarizeReports', () => {
  it('says what changed, what was kept and what failed', () => {
    expect(summarizeReports([report({ boxes_added: 3, labels_set: 12, kept_human: 2 })])).toBe(
      'Suggestions: +3 boxes, 12 labels, kept 2 of your labels (dom)',
    )
    expect(summarizeReports([report({ changed: false, boxes_added: 0, labels_set: 0 })])).toBe(
      'Suggestions: nothing new (dom)',
    )
    expect(
      summarizeReports([report(), report({ suggester: 'rule', error: 'ValueError: bad' })]),
    ).toBe('Suggestions: +1 box, 1 label (dom). rule failed: ValueError: bad')
  })
})
