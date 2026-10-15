import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import type { Annotation } from '../api/annotation'
import type { PageResponse } from '../api/types'
import { buildKeymap } from '../keyboard/keymap'
import { useLabelKeys } from '../keyboard/useLabelKeys'
import { initialState, useAppStore } from '../state/store'
import { loadWebUi } from '../test/webUi'
import { PresetPanel } from './PresetPanel'

const KEYMAP = buildKeymap(loadWebUi())

function box(id: string, labels: Record<string, string> = {}): Annotation {
  return { id, kind: 'element', bbox: [0, 0, 10, 10], labels, source: 'human', status: 'accepted' }
}

function load(boxes: Annotation[]) {
  const page: PageResponse = {
    project: 'demo',
    etag: '"v1"',
    has_dom: false,
    strips: { height: 2048, count: 1 },
    annotations: {
      schema_version: '1.0',
      taxonomy: { id: 'web-ui', version: '1.0' },
      page: { id: 'p', image: 'page.png', width: 1920, height: 2000 },
      annotations: boxes,
    },
  }
  useAppStore.getState().pageLoaded('p', page)
}

function WithKeys() {
  useLabelKeys(KEYMAP)
  return <PresetPanel presets={KEYMAP.presets} attributeIds={['Form', 'Function', 'Component']} />
}

const store = () => useAppStore.getState()
const labels = (id: string) => store().page!.annotations.annotations.find((b) => b.id === id)!.labels

describe('PresetPanel', () => {
  beforeEach(() => {
    useAppStore.setState(initialState)
    load([box('a'), box('b', { Form: 'Image', Function: 'Link', Component: 'Blank' })])
  })

  it('shows the nine presets from the YAML with their keys', () => {
    render(<PresetPanel presets={KEYMAP.presets} attributeIds={['Form', 'Function', 'Component']} />)
    const list = screen.getByRole('group', { name: 'Presets' })
    const buttons = within(list).getAllByRole('button', { name: /^Preset/ })
    expect(buttons).toHaveLength(9)
    expect(buttons[0]).toHaveAccessibleName('Preset 1: Typo · Text · Blank')
    expect(buttons[2]).toHaveAccessibleName('Preset 3: Typo · Heading · Blank')
  })

  it('is disabled until boxes are selected', () => {
    render(<PresetPanel presets={KEYMAP.presets} attributeIds={['Form', 'Function', 'Component']} />)
    expect(screen.getByRole('button', { name: /^Preset 1/ })).toBeDisabled()
  })

  it('a click applies the preset to the selection', async () => {
    store().select(['a'])
    render(<PresetPanel presets={KEYMAP.presets} attributeIds={['Form', 'Function', 'Component']} />)
    await userEvent.click(screen.getByRole('button', { name: /^Preset 3/ }))
    expect(labels('a')).toEqual({ Form: 'Typo', Function: 'Heading', Component: 'Blank' })
  })

  it('marks the preset the whole selection already matches', () => {
    store().select(['b'])
    render(<PresetPanel presets={KEYMAP.presets} attributeIds={['Form', 'Function', 'Component']} />)
    expect(screen.getByRole('button', { name: /^Preset 2/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /^Preset 1/ })).toHaveAttribute('aria-pressed', 'false')
  })

  it('a brush button starts and stops painting with that preset (3.5)', async () => {
    render(<PresetPanel presets={KEYMAP.presets} attributeIds={['Form', 'Function', 'Component']} />)
    const brush = screen.getByRole('button', { name: 'Paint with preset 3' })
    expect(brush).toBeEnabled() // painting needs no selection
    await userEvent.click(brush)
    expect(store().paint?.key).toBe('3')
    expect(brush).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText(/Painting preset 3/)).toBeInTheDocument()
    await userEvent.click(brush)
    expect(store().paint).toBeNull()
  })

  it('p shows a prompt for the preset digit', () => {
    render(<WithKeys />)
    act(() => {
      fireEvent.keyDown(window, { key: 'p' })
    })
    expect(screen.getByText(/Paint: press a preset digit/)).toBeInTheDocument()
  })

  it('pressing a digit applies the preset (one keystroke)', () => {
    store().select(['a', 'b'])
    render(<WithKeys />)
    act(() => {
      fireEvent.keyDown(window, { key: '1' })
    })
    expect(labels('a')).toEqual({ Form: 'Typo', Function: 'Text', Component: 'Blank' })
    expect(labels('b')).toEqual({ Form: 'Typo', Function: 'Text', Component: 'Blank' })
  })
})
