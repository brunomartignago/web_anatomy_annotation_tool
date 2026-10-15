// Label inheritance from section and component boxes (roadmap 3.4a).
//
// An attribute marked `inherit_from_parent: true` in the taxonomy (in web-ui.yaml:
// Component and the template section) flows to each box from the smallest section or
// component box that contains it (by the box's centre) and has that attribute set.
// Inherited values carry `label_sources[attr] = 'inherited'`; a value from any other
// source (human, legacy, preset, a suggester…) is never touched.
//
// Runs inside the edit that changed something, so a section relabel and all the children
// that follow it are one undo step. It never runs on load, so opening a page changes nothing.

import type { Draft } from 'immer'

import type { Annotation, PageAnnotationFileV1 } from '../api/annotation'

type Box = Annotation | Draft<Annotation>

export const isContainer = (box: Box) => box.kind === 'section' || box.kind === 'component'

const area = (box: Box) => box.bbox[2] * box.bbox[3]

function containsCentre(outer: Box, inner: Box): boolean {
  const [x, y, w, h] = outer.bbox
  const cx = inner.bbox[0] + inner.bbox[2] / 2
  const cy = inner.bbox[1] + inner.bbox[3] / 2
  return cx >= x && cx <= x + w && cy >= y && cy <= y + h
}

/** Recompute inherited labels and `parent_id` on a draft of the page's annotations. */
export function applyInheritance(doc: Draft<PageAnnotationFileV1>, inheritable: string[]): void {
  const containers = doc.annotations.filter(isContainer)

  for (const box of doc.annotations) {
    if (box.status === 'rejected') continue
    // Containers around this box, smallest first. Only strictly larger boxes can contain
    // it, so two sections never inherit from each other.
    const around = containers
      .filter((c) => c.id !== box.id && c.status !== 'rejected')
      .filter((c) => area(c) > area(box) && containsCentre(c, box))
      .sort((a, b) => area(a) - area(b))

    const parentId = around[0]?.id
    if (parentId !== undefined) {
      if (box.parent_id !== parentId) box.parent_id = parentId
    } else if (box.parent_id != null) {
      delete box.parent_id
    }

    for (const attr of inheritable) {
      const source = box.label_sources?.[attr]
      const own = Boolean(box.labels[attr]) && source !== 'inherited'
      if (own) continue
      const provider = around.find((c) => c.labels[attr])
      if (provider) {
        const value = provider.labels[attr]
        if (box.labels[attr] !== value) box.labels[attr] = value
        if (source !== 'inherited') box.label_sources = { ...box.label_sources, [attr]: 'inherited' }
      } else if (source === 'inherited') {
        delete box.labels[attr]
        delete box.label_sources![attr]
      }
    }
  }
}
