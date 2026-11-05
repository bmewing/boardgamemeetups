import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '../../test/render'
import { dealRound, nextGame, type Game, type Row } from './pickDemo'
import { TonightsPickDemo } from './TonightsPickDemo'

const rows: Row[] = [
  { name: 'Catan', min: 3, max: 4, owner: 0, fits: false, votes: 0 },
  { name: 'Codenames', min: 2, max: 8, owner: 1, fits: true, votes: 2 },
  { name: 'Heat', min: 1, max: 6, owner: 2, fits: true, votes: 5 },
]

describe('TonightsPickDemo', () => {
  it('holds on the finished pick when it can’t animate', () => {
    renderWithProviders(<TonightsPickDemo />)

    expect(screen.getByTestId('demo-round')).toHaveTextContent("Round 1 · Tonight's pick")
    // The crowned game is the one named in the middle of the table.
    const winner = screen.getByText('Tonight').nextElementSibling!.textContent!
    expect(screen.getByText('Pick').closest('[data-winner]')).toHaveTextContent(winner)
  })

  it('deals hands with at least three games that fit and two that don’t', () => {
    for (let i = 0; i < 50; i++) {
      const hand = dealRound()
      expect(hand.filter((r) => r.fits).length).toBeGreaterThanOrEqual(3)
      expect(hand.filter((r) => !r.fits).length).toBeGreaterThanOrEqual(2)
      const votes = hand.filter((r) => r.fits).map((r) => r.votes)
      expect(new Set(votes).size).toBe(votes.length)
    }
  })

  it('walks every phase, then starts a fresh round', () => {
    let game: Game = { round: 1, rows, phase: 'rsvp', n: 0 }
    const phases: string[] = []
    for (let i = 0; i < 40 && game.round === 1; i++) {
      if (phases.at(-1) !== game.phase) phases.push(game.phase)
      ;[game] = nextGame(game, () => rows)
    }

    expect(phases).toEqual(['rsvp', 'pool', 'fit', 'vote', 'pick'])
    expect(game).toEqual({ round: 2, rows, phase: 'rsvp', n: 0 })
  })
})
