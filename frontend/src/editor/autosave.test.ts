import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { PageResponse } from '../api/types'
import { initialState, useAppStore } from '../state/store'
import { AUTOSAVE_DELAY_MS, saveNow, useAutosave } from './autosave'

const store = () => useAppStore.getState()
const progress = { boxes: 1, empty: 1, partial: 0, complete: 0, suggested: 0, labeled: {} }

const PAGE: PageResponse = {
  project: 'demo',
  etag: '"v1"',
  has_dom: false,
  strips: { height: 2048, count: 1 },
  annotations: {
    schema_version: '1.0',
    taxonomy: { id: 'web-ui', version: '1.0' },
    page: { id: 'p', image: 'page.png', width: 1920, height: 2000 },
    annotations: [],
  },
}

type Reply = { status: number; body: unknown }

function mockSaves(...replies: Reply[]) {
  let n = 0
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
    void init
    const reply = replies[Math.min(n++, replies.length - 1)]
    return new Response(JSON.stringify(reply.body), { status: reply.status })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const ok = (etag: string): Reply => ({ status: 200, body: { etag, progress } })

async function flush(ms = AUTOSAVE_DELAY_MS) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

describe('autosave', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    useAppStore.setState({ ...initialState, project: 'demo' })
    store().pageLoaded('p', PAGE)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('saves once, 800 ms after the last of several quick edits', async () => {
    const fetchMock = mockSaves(ok('"v2"'))
    renderHook(() => useAutosave())
    act(() => {
      store().addBox([0, 0, 10, 10])
    })
    await flush(500)
    act(() => {
      store().addBox([20, 0, 10, 10])
    })
    await flush(500)
    expect(fetchMock).not.toHaveBeenCalled() // still within 800 ms of the last edit
    await flush(400)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/pages/p/annotations?project=demo')
    expect(init?.method).toBe('PUT')
    expect((init?.headers as Record<string, string>)['If-Match']).toBe('"v1"')
    expect(JSON.parse(init?.body as string).annotations).toHaveLength(2)
    expect(store().saveState).toBe('saved')
    expect(store().page!.etag).toBe('"v2"')
  })

  it('saves after undo too (AUDIT #7)', async () => {
    const fetchMock = mockSaves(ok('"v2"'), ok('"v3"'))
    renderHook(() => useAutosave())
    act(() => {
      store().addBox([0, 0, 10, 10])
    })
    await flush()
    act(() => {
      store().undo()
    })
    await flush()

    expect(fetchMock).toHaveBeenCalledTimes(2)
    const second = JSON.parse(fetchMock.mock.calls[1][1]?.body as string)
    expect(second.annotations).toHaveLength(0)
    const headers = fetchMock.mock.calls[1][1]?.headers as Record<string, string>
    expect(headers['If-Match']).toBe('"v2"') // uses the etag from the previous save
  })

  it('stops on a conflict and never overwrites the newer file', async () => {
    const fetchMock = mockSaves({ status: 412, body: { detail: 'changed', etag: '"other"' } })
    renderHook(() => useAutosave())
    act(() => {
      store().addBox([0, 0, 10, 10])
    })
    await flush()
    expect(store().saveState).toBe('conflict')

    act(() => {
      store().addBox([20, 0, 10, 10])
    })
    await flush()
    expect(fetchMock).toHaveBeenCalledTimes(1) // no further attempts
  })

  it('reports other errors and retries after the next edit', async () => {
    const fetchMock = mockSaves({ status: 500, body: { detail: 'disk full' } }, ok('"v2"'))
    renderHook(() => useAutosave())
    act(() => {
      store().addBox([0, 0, 10, 10])
    })
    await flush()
    expect(store().saveState).toBe('error')
    expect(store().saveError).toContain('disk full')

    act(() => {
      store().addBox([20, 0, 10, 10])
    })
    await flush()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(store().saveState).toBe('saved')
  })

  it('saveNow flushes immediately, e.g. before switching pages', async () => {
    const fetchMock = mockSaves(ok('"v2"'))
    act(() => {
      store().addBox([0, 0, 10, 10])
    })
    await act(async () => {
      await saveNow()
    })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(store().saveState).toBe('saved')
  })

  it('does nothing when there is nothing to save', async () => {
    const fetchMock = mockSaves(ok('"v2"'))
    await act(async () => {
      await saveNow()
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
