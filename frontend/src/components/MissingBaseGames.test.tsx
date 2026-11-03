import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import type { MissingBaseGames } from '../api/collection'
import type { GameSummary } from '../api/games'
import { mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { FindMissingBaseGames } from './MissingBaseGames'

const game = (id: number, name: string, isExpansion = false): GameSummary => ({
  id,
  name,
  year_published: 2024,
  is_expansion: isExpansion,
  thumbnail_url: null,
  min_players: 2,
  max_players: 4,
  min_playtime: 60,
  max_playtime: 120,
  weight: 3.5,
  bgg_rank: null,
  best_with: [],
  base_game_ids: [],
})
const brief = (g: GameSummary) => ({
  id: g.id,
  name: g.name,
  year_published: g.year_published,
  thumbnail_url: null,
  is_expansion: g.is_expansion,
})

const found: MissingBaseGames = {
  suggestions: [
    {
      game: game(1, 'Arcs'),
      expansions: [brief(game(2, 'Arcs: The Blighted Reach Expansion', true))],
      ownership: null,
      on_wishlist: false,
    },
  ],
  choices: [
    {
      expansion: brief(game(3, 'Dice Throne: Adventures', true)),
      options: [game(4, 'Dice Throne: Season One'), game(5, 'Dice Throne')],
      option_count: 18,
    },
  ],
  unchecked: 0,
  hidden: 1,
}

describe('FindMissingBaseGames', () => {
  beforeEach(() => {
    signIn()
  })

  it('suggests base games for owned expansions and adds the one you own', async () => {
    const saved: { url: string; body: unknown }[] = []
    mockApi({
      'POST /api/me/games/missing-base-games': () => Response.json(found),
      'PUT /api/me/games/1': async (request) => {
        saved.push({ url: new URL(request.url).pathname, body: await request.json() })
        return Response.json({})
      },
      'GET /api/me/games': () => Response.json([]),
    })
    renderWithProviders(<FindMissingBaseGames />)

    await userEvent.click(screen.getByRole('button', { name: 'Find missing base games' }))

    expect(await screen.findByText('Arcs')).toBeInTheDocument()
    expect(screen.getByText(/For your expansion: Arcs: The Blighted Reach/)).toBeInTheDocument()
    expect(screen.getByText(/works with 18 games/)).toBeInTheDocument()
    expect(screen.getByText('or search the other 16')).toBeInTheDocument()
    expect(screen.getByText(/1 game you said you're not interested in/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'I own it' }))

    await waitFor(() => expect(screen.queryByText('Arcs')).not.toBeInTheDocument())
    expect(saved).toEqual([{ url: '/api/me/games/1', body: { ownership: 'owned' } }])
  })

  it('says so when nothing is missing', async () => {
    mockApi({
      'POST /api/me/games/missing-base-games': () =>
        Response.json({ suggestions: [], choices: [], unchecked: 0, hidden: 0 }),
    })
    renderWithProviders(<FindMissingBaseGames />)

    await userEvent.click(screen.getByRole('button', { name: 'Find missing base games' }))

    expect(await screen.findByText(/Every expansion you own has its base game/)).toBeInTheDocument()
  })

  it('asks again while BGG lookups make progress', async () => {
    const answers = [
      { ...found, unchecked: 50 },
      { ...found, unchecked: 10 },
      { ...found, unchecked: 0 },
    ]
    let calls = 0
    mockApi({
      'POST /api/me/games/missing-base-games': () => Response.json(answers[calls++]),
    })
    renderWithProviders(<FindMissingBaseGames />)

    await userEvent.click(screen.getByRole('button', { name: 'Find missing base games' }))

    expect(await screen.findByText('Arcs')).toBeInTheDocument()
    expect(calls).toBe(3)
  })
})
