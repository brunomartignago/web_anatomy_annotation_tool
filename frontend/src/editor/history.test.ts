import { describe, expect, it } from 'vitest'

import { HISTORY_LIMIT, edit, emptyHistory, redo, undo } from './history'

interface Doc {
  boxes: { id: string; x: number }[]
}

const start: Doc = { boxes: [{ id: 'a', x: 1 }] }

const addB = (d: Doc) => {
  d.boxes.push({ id: 'b', x: 2 })
}
const moveA = (d: Doc) => {
  d.boxes[0].x = 10
}

describe('history', () => {
  it('undoes and redoes an edit exactly', () => {
    const one = edit(start, emptyHistory(), addB)
    expect(one.doc.boxes.map((b) => b.id)).toEqual(['a', 'b'])
    expect(start.boxes).toHaveLength(1) // the original is never mutated

    const back = undo(one.doc, one.history)!
    expect(back.doc).toEqual(start)
    const again = redo(back.doc, back.history)!
    expect(again.doc).toEqual(one.doc)
  })

  it('undoes several edits in reverse order', () => {
    const one = edit(start, emptyHistory(), addB)
    const two = edit(one.doc, one.history, moveA)
    const u1 = undo(two.doc, two.history)!
    expect(u1.doc).toEqual(one.doc)
    const u2 = undo(u1.doc, u1.history)!
    expect(u2.doc).toEqual(start)
    expect(undo(u2.doc, u2.history)).toBeNull() // nothing left
  })

  it('a new edit clears the redo stack', () => {
    const one = edit(start, emptyHistory(), addB)
    const back = undo(one.doc, one.history)!
    const other = edit(back.doc, back.history, moveA)
    expect(redo(other.doc, other.history)).toBeNull()
  })

  it('an edit that changes nothing is not recorded', () => {
    const same = edit(start, emptyHistory(), () => {})
    expect(same.doc).toBe(start)
    expect(same.history.undo).toHaveLength(0)
  })

  it(`keeps at most ${HISTORY_LIMIT} steps`, () => {
    let state = { doc: { boxes: [] as { id: string; x: number }[] }, history: emptyHistory() }
    for (let i = 0; i < HISTORY_LIMIT + 10; i++) {
      state = edit(state.doc, state.history, (d) => {
        d.boxes.push({ id: String(i), x: i })
      })
    }
    expect(state.history.undo).toHaveLength(HISTORY_LIMIT)
  })
})
