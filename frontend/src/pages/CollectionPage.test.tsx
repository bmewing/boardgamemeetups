import { screen, waitFor } from '@testing-library/react'
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
  base_game_ids: [],
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

  it('removes a game from the list after asking once', async () => {
    let current = rows
    const deleted: string[] = []
    mockApi({
      'GET /api/me/games': () => Response.json(current),
      'POST /api/me/games/fill-details': () => Response.json({ filled: 0, remaining: 0 }),
      'DELETE /api/me/games/1': (request) => {
        deleted.push(new URL(request.url).pathname)
        current = current.filter((r) => r.game.id !== 1)
        return new Response(null, { status: 204 })
      },
    })
    renderWithProviders(<CollectionPage />)

    await userEvent.click(await screen.findByRole('button', { name: 'Remove Azul' }))
    expect(screen.getByText(/Anything you recorded about it goes too/)).toBeInTheDocument()
    expect(deleted).toEqual([])
    await userEvent.click(screen.getByRole('button', { name: 'Remove' }))

    await waitFor(() => expect(screen.queryByText('Azul')).not.toBeInTheDocument())
    expect(deleted).toEqual(['/api/me/games/1'])
    expect(screen.getByText('Brass')).toBeInTheDocument()
  })

  it('offers to remove the expansions of a base game along with it', async () => {
    const base = game(10, 'Disaster Looms!')
    const listed = [
      row(base),
      row(game(11, 'Disaster Looms!: CEOs', { is_expansion: true, base_game_ids: [10] })),
      row(game(12, 'Disaster Looms!: Founders', { is_expansion: true, base_game_ids: [10] })),
      // Also fits Azul, which stays in the list, so it isn't offered.
      row(game(13, 'Shared Pack', { is_expansion: true, base_game_ids: [10, 1] })),
      row(game(1, 'Azul')),
    ]
    let removed: URL | null = null
    mockApi({
      'GET /api/me/games': () => Response.json(listed),
      'POST /api/me/games/fill-details': () => Response.json({ filled: 0, remaining: 0 }),
      'DELETE /api/me/games/10': (request) => {
        removed = new URL(request.url)
        return new Response(null, { status: 204 })
      },
    })
    renderWithProviders(<CollectionPage />)

    await userEvent.click(await screen.findByRole('button', { name: 'Remove Disaster Looms!' }))
    const option = screen.getByRole('checkbox', { name: 'Also remove its 2 expansions' })
    expect(option).toBeChecked()
    expect(screen.getByText('Disaster Looms!: CEOs, Disaster Looms!: Founders')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Remove' }))

    await waitFor(() => expect(removed).not.toBeNull())
    expect(removed!.searchParams.getAll('expansions')).toEqual(['11', '12'])
  })

  it('removes only the base game when the expansions are unticked', async () => {
    const listed = [
      row(game(10, 'Disaster Looms!')),
      row(game(11, 'Disaster Looms!: CEOs', { is_expansion: true, base_game_ids: [10] })),
    ]
    let removed: URL | null = null
    mockApi({
      'GET /api/me/games': () => Response.json(listed),
      'POST /api/me/games/fill-details': () => Response.json({ filled: 0, remaining: 0 }),
      'DELETE /api/me/games/10': (request) => {
        removed = new URL(request.url)
        return new Response(null, { status: 204 })
      },
    })
    renderWithProviders(<CollectionPage />)

    await userEvent.click(await screen.findByRole('button', { name: 'Remove Disaster Looms!' }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'Also remove its expansion' }))
    await userEvent.click(screen.getByRole('button', { name: 'Remove' }))

    await waitFor(() => expect(removed).not.toBeNull())
    expect(removed!.searchParams.getAll('expansions')).toEqual([])
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
