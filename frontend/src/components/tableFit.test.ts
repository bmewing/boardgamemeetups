import { describe, expect, it } from 'vitest'

import { capacityNote } from './tableFit'

describe('capacityNote', () => {
  it('says nothing when everyone fits at one table', () => {
    expect(capacityNote(2, 4, 'together', 4)).toBeNull()
    expect(capacityNote(2, 4, null, 0)).toBeNull() // nobody going yet
  })

  it('flags too many people', () => {
    expect(capacityNote(2, 4, null, 5)).toEqual({
      text: 'Too many: seats up to 4, 5 going',
      color: 'red',
    })
  })

  it('softens it when the group would split into tables', () => {
    expect(capacityNote(2, 4, 'split', 5)).toEqual({
      text: 'Seats up to 4: 5 going means splitting up',
      color: 'yellow',
    })
  })

  it('flags too few people and unknown counts', () => {
    expect(capacityNote(3, 5, null, 2)?.text).toBe('Too few: needs 3, 2 going')
    expect(capacityNote(null, null, null, 3)?.color).toBe('gray')
  })
})
