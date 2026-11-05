import { describe, expect, it } from 'vitest'

import { playerRange, widenedLabel } from './gameFacts'

const players = (min: number | null, max: number | null) => ({
  min_players: min,
  max_players: max,
})

describe('playerRange', () => {
  it('takes the widest range of a game and its expansions', () => {
    expect(playerRange(players(2, 4), [players(2, 6), players(1, 1)])).toEqual(players(1, 6))
  })

  it("never narrows a game's range", () => {
    expect(playerRange(players(2, 5), [players(3, 4)])).toEqual(players(2, 5))
  })

  it("stays unknown while the game's own maximum is", () => {
    expect(playerRange(players(2, null), [players(2, 6)])).toEqual(players(2, null))
  })
})

describe('widenedLabel', () => {
  it('says how many a game seats only when expansions change it', () => {
    expect(widenedLabel(players(2, 4), players(1, 6))).toBe('seats 1–6')
    expect(widenedLabel(players(2, 4), players(2, 4))).toBeNull()
  })
})
