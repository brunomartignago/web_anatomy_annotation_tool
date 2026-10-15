import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { useEffect } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Annotation } from '../api/annotation'
import type { PageResponse } from '../api/types'
import { LabelPanel } from '../panels/LabelPanel'
import { initialState, useAppStore } from '../state/store'
import { loadWebUi } from '../test/webUi'
import { CheatSheet } from './CheatSheet'
import { buildKeymap } from './keymap'
import { useLabelKeys } from './useLabelKeys'

const WEB_UI = loadWebUi()
const KEYMAP = buildKeymap(WEB_UI)
const HOTKEYS = Object.fromEntries(KEYMAP.attributes.map((a) => [a.id, a.hotkey]))

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

/** The label keys plus a stand-in for the canvas's own key handler (bubble phase). */
function Harness({ canvasKeys }: { canvasKeys: (key: string) => void }) {
  useLabelKeys(KEYMAP)
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => canvasKeys(event.key)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [canvasKeys])
  return <LabelPanel attributes={WEB_UI.attributes} hotkeys={HOTKEYS} />
}

const store = () => useAppStore.getState()
const press = (key: string) =>
  act(() => {
    fireEvent.keyDown(window, { key })
  })
const labels = (id: string) => store().page!.annotations.annotations.find((b) => b.id === id)!.labels

describe('label keys', () => {
  beforeEach(() => {
    useAppStore.setState(initialState)
    store().pageLoaded('p', PAGE)
  })

  it('n then h labels every selected box Heading (two keystrokes)', () => {
    store().select(['a', 'b'])
    render(<Harness canvasKeys={() => {}} />)

    press('n')
    expect(store().picker).toBe('Function')
    const fn = screen.getByRole('group', { name: 'Function' })
    expect(fn).toHaveAttribute('aria-current', 'true') // the focused attribute is visible
    expect(screen.getByText(/Function: press a letter/)).toBeInTheDocument()

    press('h')
    expect(labels('a').Function).toBe('Heading')
    expect(labels('b').Function).toBe('Heading')
    expect(store().picker).toBeNull()
    expect(fn).not.toHaveAttribute('aria-current')
  })

  it('inside a picker, letters go to the picker and not to the canvas', () => {
    store().select(['a'])
    const canvasKeys = vi.fn()
    render(<Harness canvasKeys={canvasKeys} />)
    press('n')
    press('d') // Dropdown, not "draw tool"
    expect(labels('a').Function).toBe('Dropdown')
    expect(canvasKeys).not.toHaveBeenCalled()

    press('d') // picker closed again: now it's the canvas's draw key
    expect(canvasKeys).toHaveBeenCalledWith('d')
  })

  it('Escape closes the picker without labeling', () => {
    store().select(['a'])
    render(<Harness canvasKeys={() => {}} />)
    press('t')
    press('Escape')
    expect(store().picker).toBeNull()
    expect(labels('a')).toEqual({})
  })

  it('does nothing without a selection', () => {
    const canvasKeys = vi.fn()
    render(<Harness canvasKeys={canvasKeys} />)
    press('f')
    expect(store().picker).toBeNull()
    expect(canvasKeys).toHaveBeenCalledWith('f')
  })

  it('shows each option letter next to its button', () => {
    store().select(['a'])
    render(<Harness canvasKeys={() => {}} />)
    const heading = screen.getByRole('button', { name: 'Heading' }) // the letter is aria-hidden
    expect(heading).toHaveTextContent('hHeading')
  })

  it('? toggles the cheat sheet', () => {
    render(<Harness canvasKeys={() => {}} />)
    press('?')
    expect(store().cheatSheet).toBe(true)
    press('Escape')
    expect(store().cheatSheet).toBe(false)
  })
})

describe('CheatSheet', () => {
  it('lists every attribute hotkey and option letter from the taxonomy', () => {
    render(<CheatSheet keymap={KEYMAP} onClose={() => {}} />)
    const dialog = screen.getByRole('dialog', { name: 'Keyboard shortcuts' })
    const sections = KEYMAP.attributes.map((a) => within(dialog).getByRole('region', { name: a.label }))
    expect(sections).toHaveLength(4)
    const fn = within(dialog).getByRole('region', { name: 'Function' })
    expect(fn).toHaveTextContent('n Function')
    expect(fn).toHaveTextContent('hHeading')
    expect(within(dialog).getByRole('region', { name: 'Template section' })).toHaveTextContent(
      'nRight Menu',
    )
  })
})
