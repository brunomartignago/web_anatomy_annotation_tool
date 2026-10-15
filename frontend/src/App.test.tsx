import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { initialState, useAppStore } from './state/store'

const responses: Record<string, unknown> = {
  '/api/taxonomy': {
    id: 'web-ui',
    version: '1.0',
    name: 'Web UI taxonomy',
    attributes: [],
    presets: [],
    rules: {},
  },
  '/api/projects': { current: 'demo', projects: [{ name: 'demo', pages: 2 }] },
  '/api/projects/demo/pages': [
    {
      id: 'edition_cnn_com',
      blocked: false,
      blocked_reasons: [],
      has_annotations: true,
      has_image: true,
      has_dom: true,
      strips: 4,
      progress: { boxes: 210, empty: 0, partial: 0, complete: 210, suggested: 0, labeled: {} },
    },
    {
      id: 'www_adobe_com',
      blocked: true,
      blocked_reasons: ['HTTP 403'],
      has_annotations: false,
      has_image: true,
      has_dom: true,
      strips: 1,
      progress: { boxes: 0, empty: 0, partial: 0, complete: 0, suggested: 0, labeled: {} },
    },
  ],
}

function mockServer(ok = true) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string) => {
      if (!ok) return new Response(JSON.stringify({ detail: 'server down' }), { status: 503 })
      if (!(path in responses)) {
        return new Response(JSON.stringify({ detail: 'not found' }), { status: 404 })
      }
      return new Response(JSON.stringify(responses[path]), { status: 200 })
    }),
  )
}

describe('App', () => {
  beforeEach(() => {
    useAppStore.setState(initialState)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('lists the served project and its pages with progress', async () => {
    mockServer()
    render(<App />)

    const list = await screen.findByRole('list', { name: 'Pages' })
    expect(screen.getByText('demo')).toBeInTheDocument()
    expect(screen.getByText('Web UI taxonomy v1.0')).toBeInTheDocument()
    expect(within(list).getByText('210/210 boxes complete')).toBeInTheDocument()
    expect(within(list).getByText('blocked')).toBeInTheDocument()
  })

  it('opens a page when it is clicked', async () => {
    mockServer()
    render(<App />)

    const adobe = await screen.findByRole('button', { name: /www_adobe_com/ })
    expect(adobe).not.toHaveAttribute('aria-current')
    await userEvent.click(adobe)
    expect(adobe).toHaveAttribute('aria-current', 'true')
  })

  it('] and [ move through the page queue', async () => {
    mockServer()
    render(<App />)
    const cnn = await screen.findByRole('button', { name: /edition_cnn_com/ })
    const adobe = screen.getByRole('button', { name: /www_adobe_com/ })
    expect(cnn).toHaveAttribute('aria-current', 'true')
    await userEvent.keyboard(']')
    expect(adobe).toHaveAttribute('aria-current', 'true')
    await userEvent.keyboard(']') // already the last page
    expect(adobe).toHaveAttribute('aria-current', 'true')
    await userEvent.keyboard('[[') // user-event syntax for a literal "["
    expect(cnn).toHaveAttribute('aria-current', 'true')
  })

  it('explains how to start the server when the API is unreachable', async () => {
    mockServer(false)
    render(<App />)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('server down')
    expect(alert).toHaveTextContent('annotool serve')
  })
})
