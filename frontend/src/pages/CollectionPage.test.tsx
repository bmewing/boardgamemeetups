import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import type { UserGame } from '../api/collection'
import type { GameSummary } from '../api/games'
import { mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { CollectionPage } from './CollectionPage'

const game = (id: number, name: string, extra: Partial<GameSummary> = {}): GameSummary => ({
  id,
  name,
  year_published: 2020,
  is_expansion: false,
  thumbnail_url: null,
  min_players: 2,
  max_players: 4,
  min_playtime: 30,
  max_playtime: 45,
  weight: 1.8,
  bgg_rank: null,
  best_with: [],
  ...extra,
})

const row = (g: GameSummary, extra: Partial<UserGame> = {}): UserGame => ({
  game: g,
  ownership: 'owned',
  wishlist_priority: null,
  want_to_play: false,
  rating: null,
  weight_vote: null,
  playtime_feel: null,
  can_teach: false,
  teach_minutes: null,
  plays: 0,
  will_bring: true,
  notes: null,
  player_counts: [],
  moods: [],
  source: 'bgg',
  updated_at: '2026-11-03T12:00:00Z',
  ...extra,
})

const rows = [
  row(game(1, 'Azul'), { rating: 8 }),
  row(game(2, 'Brass', { min_players: 3, max_playtime: 120, weight: 3.9 })),
  row(game(3, 'Cascadia'), { ownership: null, wishlist_priority: 2 }),
]

describe('CollectionPage', () => {
  beforeEach(() => {
    signIn()
  })

  it('shows owned games with your answers, and fetches missing details', async () => {
    let filled = 0
    mockApi({
      'GET /api/me/games': () => Response.json(rows),
      'POST /api/me/games/fill-details': () => {
        filled += 1
        return Response.json({ filled: 0, remaining: 0 })
      },
    })
    renderWithProviders(<CollectionPage />)

    expect(await screen.findByText('Azul')).toBeInTheDocument()
    expect(screen.getByText('Rated 8')).toBeInTheDocument()
    expect(screen.queryByText('Cascadia')).not.toBeInTheDocument()
    expect(screen.getByText('2 of 3 games')).toBeInTheDocument()
    expect(filled).toBeGreaterThan(0)
  })

  it('filters by shelf, player count, length and weight', async () => {
    mockApi({
      'GET /api/me/games': () => Response.json(rows),
      'POST /api/me/games/fill-details': () => Response.json({ filled: 0, remaining: 0 }),
    })
    renderWithProviders(<CollectionPage />)
    await screen.findByText('Azul')

    await userEvent.click(screen.getByText('Wishlist & want to play'))
    expect(screen.getByText('Cascadia')).toBeInTheDocument()
    expect(screen.getByText('Wishlist: Love to have')).toBeInTheDocument()
    expect(screen.queryByText('Azul')).not.toBeInTheDocument()

    await userEvent.click(screen.getByText('Owned'))
    await userEvent.type(screen.getByLabelText('Players'), '2')
    expect(screen.queryByText('Brass')).not.toBeInTheDocument()
    await userEvent.clear(screen.getByLabelText('Players'))

    await userEvent.type(screen.getByLabelText('Max minutes'), '60')
    expect(screen.queryByText('Brass')).not.toBeInTheDocument()
    expect(screen.getByText('Azul')).toBeInTheDocument()
  })

  it('points to BGG and search when the list is empty', async () => {
    mockApi({ 'GET /api/me/games': () => Response.json([]) })
    renderWithProviders(<CollectionPage />)

    expect(await screen.findByText(/No games yet/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Pull from BGG' })).toHaveAttribute(
      'href',
      '/collection/pull',
    )
  })
})
