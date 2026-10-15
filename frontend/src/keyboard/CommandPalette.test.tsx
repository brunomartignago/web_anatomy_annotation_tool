import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Annotation } from '../api/annotation'
import type { PageResponse } from '../api/types'
import { initialState, useAppStore } from '../state/store'
import { loadWebUi } from '../test/webUi'
import { CommandPalette } from './CommandPalette'
import { buildKeymap } from './keymap'
import { buildCommands } from './palette'
import { useLabelKeys } from './useLabelKeys'

const KEYMAP = buildKeymap(loadWebUi())
const COMMANDS = buildCommands(KEYMAP)

function box(id: string): Annotation {
  return { id, kind: 'element', bbox: [0, 0, 10, 10], labels: {}, source: 'human', status: 'accepted' }
}

const PAGE: PageResponse = {
  project: 'demo',
  etag: '"v1"',
  has_dom: false,
  strips: { height: 2048, count: 1 },
  annotations: {
    schema_version: '1.0',
    taxonomy: { id: 'web-ui', version: '1.0' },
    page: { id: 'p', image: 'page.png', width: 1920, height: 2000 },
    annotations: [box('a'), box('b')],
  },
}

const store = () => useAppStore.getState()
const labels = (id: string) => store().page!.annotations.annotations.find((b) => b.id === id)!.labels

beforeEach(() => {
  useAppStore.setState(initialState)
  store().pageLoaded('p', PAGE)
})

describe('CommandPalette', () => {
  it('"hea" then Enter labels the selection Heading (✅ 3.3)', async () => {
    store().select(['a', 'b'])
    const onClose = vi.fn()
    render(<CommandPalette commands={COMMANDS} onClose={onClose} />)
    const input = screen.getByRole('combobox', { name: 'Search labels and presets' })
    expect(input).toHaveFocus()

    await userEvent.type(input, 'hea')
    const options = screen.getAllByRole('option')
    expect(options[0]).toHaveTextContent('Heading')
    expect(options[0]).toHaveAttribute('aria-selected', 'true')

    await userEvent.keyboard('{Enter}')
    expect(labels('a').Function).toBe('Heading')
    expect(labels('b').Function).toBe('Heading')
    expect(onClose).toHaveBeenCalled()
  })

  it('arrow keys pick another result; presets apply all their labels', async () => {
    store().select(['a'])
    render(<CommandPalette commands={COMMANDS} onClose={() => {}} />)
    await userEvent.type(screen.getByRole('combobox'), 'preset')
    await userEvent.keyboard('{ArrowDown}{ArrowDown}') // Preset 3
    expect(screen.getAllByRole('option')[2]).toHaveAttribute('aria-selected', 'true')
    await userEvent.keyboard('{Enter}')
    expect(labels('a')).toEqual({ Form: 'Typo', Function: 'Heading', Component: 'Blank' })
  })

  it('a click applies a result', async () => {
    store().select(['a'])
    render(<CommandPalette commands={COMMANDS} onClose={() => {}} />)
    await userEvent.type(screen.getByRole('combobox'), 'rmen')
    await userEvent.click(screen.getByRole('option', { name: /Right Menu/ }))
    expect(labels('a').Taxonomy).toBe('Right Menu')
  })

  it('Escape closes without labeling', async () => {
    store().select(['a'])
    const onClose = vi.fn()
    render(<CommandPalette commands={COMMANDS} onClose={onClose} />)
    await userEvent.type(screen.getByRole('combobox'), 'hea{Escape}')
    expect(onClose).toHaveBeenCalled()
    expect(labels('a')).toEqual({})
  })

  it('without a selection it explains and applies nothing', async () => {
    render(<CommandPalette commands={COMMANDS} onClose={() => {}} />)
    expect(screen.getByText(/Select boxes first/)).toBeInTheDocument()
    await userEvent.type(screen.getByRole('combobox'), 'hea{Enter}')
    expect(labels('a')).toEqual({})
  })

  it('says so when nothing matches', async () => {
    render(<CommandPalette commands={COMMANDS} onClose={() => {}} />)
    await userEvent.type(screen.getByRole('combobox'), 'qqq')
    expect(screen.getByText(/No label or preset matches/)).toBeInTheDocument()
  })
})

describe('the / key', () => {
  function Keys() {
    useLabelKeys(KEYMAP)
    return null
  }

  it('opens the palette', () => {
    render(<Keys />)
    act(() => {
      fireEvent.keyDown(window, { key: '/' })
    })
    expect(store().palette).toBe(true)
  })
})
