import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import type { Annotation } from '../api/annotation'
import type { PageResponse, TaxonomyAttribute } from '../api/types'
import { initialState, useAppStore } from '../state/store'
import { BoxList } from './BoxList'
import { LabelPanel } from './LabelPanel'
import { ProgressPanel } from './ProgressPanel'

// A two-attribute taxonomy with one proposed option; the panels must use only this data.
const ATTRIBUTES: TaxonomyAttribute[] = [
  {
    id: 'Form',
    label: 'Form',
    hotkey: 'f',
    options: [
      { value: 'Typo', key: 't', status: 'active' },
      { value: 'Image', key: 'i', status: 'active' },
      { value: 'Hologram', key: 'h', status: 'proposed' },
    ],
    inherit_from_parent: false,
    computed_by_rules: false,
  },
  {
    id: 'Taxonomy',
    label: 'Template section',
    hotkey: 't',
    options: [
      { value: 'Header', key: 'h', status: 'active' },
      { value: 'Footer', key: 'f', status: 'active' },
    ],
    inherit_from_parent: true,
    computed_by_rules: true,
  },
]
const IDS = ATTRIBUTES.map((a) => a.id)

function box(id: string, labels: Record<string, string>): Annotation {
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

const store = () => useAppStore.getState()
const labelsOf = (id: string) => store().page!.annotations.annotations.find((b) => b.id === id)!.labels

beforeEach(() => {
  useAppStore.setState(initialState)
  load([
    box('a', { Form: 'Typo', Taxonomy: 'Header' }), // complete
    box('b', { Form: 'Image' }), // partial
    box('c', {}), // empty
  ])
})

describe('LabelPanel', () => {
  it('is built from the taxonomy and hides proposed options', () => {
    render(<LabelPanel attributes={ATTRIBUTES} />)
    expect(screen.getByRole('group', { name: 'Form' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Template section' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Hologram/ })).not.toBeInTheDocument()
  })

  it('is disabled until boxes are selected', () => {
    render(<LabelPanel attributes={ATTRIBUTES} />)
    expect(screen.getByText(/Select boxes on the canvas/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Typo' })).toBeDisabled()
  })

  it('labels every selected box with one click', async () => {
    store().select(['b', 'c'])
    render(<LabelPanel attributes={ATTRIBUTES} />)
    await userEvent.click(screen.getByRole('button', { name: 'Footer' }))
    expect(labelsOf('b').Taxonomy).toBe('Footer')
    expect(labelsOf('c').Taxonomy).toBe('Footer')
    expect(store().history.undo).toHaveLength(1) // one undo step for both
  })

  it('shows mixed values with counts', () => {
    store().select(['a', 'b', 'c'])
    render(<LabelPanel attributes={ATTRIBUTES} />)
    const form = screen.getByRole('group', { name: /Form/ })
    expect(within(form).getByText('mixed')).toBeInTheDocument()
    expect(within(form).getByRole('button', { name: 'Typo 1' })).toBeInTheDocument()
    expect(within(form).getByRole('button', { name: 'Image 1' })).toBeInTheDocument()
    expect(screen.getByText('3 selected')).toBeInTheDocument()
  })

  it('clicking the value already set keeps it (no accidental removal)', async () => {
    store().select(['a'])
    render(<LabelPanel attributes={ATTRIBUTES} />)
    const typo = screen.getByRole('button', { name: 'Typo' })
    expect(typo).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(typo)
    expect(labelsOf('a').Form).toBe('Typo')
    expect(store().docVersion).toBe(0)
  })

  it('the clear button removes the attribute from every selected box', async () => {
    store().select(['a', 'b'])
    render(<LabelPanel attributes={ATTRIBUTES} />)
    expect(screen.queryByRole('button', { name: 'Clear Template section' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Clear Form' }))
    expect(labelsOf('a').Form).toBeUndefined()
    expect(labelsOf('b').Form).toBeUndefined()
    expect(screen.queryByRole('button', { name: 'Clear Form' })).not.toBeInTheDocument()
  })

  it('switches the box kind; a section passes its Template section on (3.4a)', async () => {
    useAppStore.setState({
      taxonomy: { id: 'web-ui', version: '1.0', name: 'test', presets: [], rules: {}, attributes: ATTRIBUTES },
    })
    load([box('c', {}), { ...box('sec', { Taxonomy: 'Footer' }), bbox: [0, 0, 100, 100] }])
    store().select(['sec'])
    render(<LabelPanel attributes={ATTRIBUTES} />)
    const kinds = screen.getByRole('group', { name: 'Box kind' })
    expect(within(kinds).getByRole('button', { name: 'Element' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(within(kinds).getByRole('button', { name: 'Section' }))
    expect(store().page!.annotations.annotations[1].kind).toBe('section')
    expect(within(kinds).getByRole('button', { name: 'Section' })).toHaveAttribute('aria-pressed', 'true')
    expect(labelsOf('c').Taxonomy).toBe('Footer')
  })

  it('marks inherited values and offers no clear button for them', () => {
    load([
      {
        ...box('c', { Taxonomy: 'Header' }),
        label_sources: { Taxonomy: 'inherited' },
      },
    ])
    store().select(['c'])
    render(<LabelPanel attributes={ATTRIBUTES} />)
    const section = screen.getByRole('group', { name: 'Template section' })
    expect(within(section).getByText('inherited')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Clear Template section' })).not.toBeInTheDocument()
    expect(within(section).getByRole('button', { name: 'Header' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })
})

describe('ProgressPanel', () => {
  it('shows complete boxes and each attribute', () => {
    render(<ProgressPanel attributes={ATTRIBUTES} />)
    const value = (name: string) =>
      screen.getByRole('progressbar', { name }).getAttribute('aria-valuenow')
    expect(value('Complete boxes')).toBe('1')
    expect(value('Form')).toBe('2')
    expect(value('Template section')).toBe('1')
  })

  it('shows effort as actions per box (3.7)', () => {
    const loaded = store().page!
    store().pageLoaded('p', {
      ...loaded,
      annotations: { ...loaded.annotations, history: { actions: 6 } },
    })
    render(<ProgressPanel attributes={ATTRIBUTES} />)
    expect(screen.getByLabelText('Effort')).toHaveTextContent('6 actions · 2.0 per box')
  })

  it('shows no ratio before any box is done', () => {
    load([])
    render(<ProgressPanel attributes={ATTRIBUTES} />)
    expect(screen.getByLabelText('Effort')).toHaveTextContent('0 actions · — per box')
  })
})

describe('BoxList', () => {
  it('filters by completeness with counts', async () => {
    render(<BoxList attributeIds={IDS} />)
    const rows = () => within(screen.getByRole('list', { name: 'Box list' })).getAllByRole('button')
    expect(rows()).toHaveLength(3)
    expect(screen.getByRole('button', { name: 'Empty 1' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Partial 1' }))
    expect(rows()).toHaveLength(1)
    expect(rows()[0]).toHaveTextContent('Image')

    await userEvent.click(screen.getByRole('button', { name: 'Empty 1' }))
    expect(rows()[0]).toHaveTextContent('unlabeled')
  })

  it('a click selects the box and asks the canvas to show it', async () => {
    render(<BoxList attributeIds={IDS} />)
    await userEvent.click(screen.getByRole('button', { name: 'Box 2: Image' }))
    expect(store().selectedIds).toEqual(['b'])
    expect(store().focus?.id).toBe('b')
    expect(screen.getByRole('button', { name: 'Box 2: Image' })).toHaveAttribute(
      'aria-current',
      'true',
    )
  })

  it('names section rows, which only show under All', async () => {
    load([box('c', {}), { ...box('sec', { Taxonomy: 'Header' }), kind: 'section' }])
    render(<BoxList attributeIds={IDS} />)
    expect(screen.getByRole('button', { name: 'Section 2: Header' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'All 2' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Empty 1' }))
    expect(screen.queryByRole('button', { name: /Section 2/ })).not.toBeInTheDocument()
  })
})
