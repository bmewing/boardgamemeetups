import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import type { UserGame, UserGameUpdate } from '../api/collection'
import type { GameSummary } from '../api/games'
import { blankUserGame } from '../components/userGameFields'
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
  bgg_rating: null,
  bgg_rank: null,
  best_with: [],
  base_game_ids: [],
  is_custom: false,
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
    expect(screen.getByDisplayValue('8')).toBeInTheDocument()
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

  it("counts the expansions you own toward a game's player range", async () => {
    const withExpansion = [
      ...rows,
      row(game(4, 'Azul: Big Box', { is_expansion: true, max_players: 6, base_game_ids: [1] })),
      // Only owned expansions count.
      row(game(5, 'Brass: Solo', { is_expansion: true, min_players: 1, base_game_ids: [2] }), {
        ownership: null,
        wishlist_priority: 3,
      }),
    ]
    mockApi({
      'GET /api/me/games': () => Response.json(withExpansion),
      'POST /api/me/games/fill-details': () => Response.json({ filled: 0, remaining: 0 }),
    })
    renderWithProviders(<CollectionPage />)

    expect(await screen.findByText('With your Azul: Big Box (seats 2–6)')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Players'), '6')
    expect(screen.getByText('Azul')).toBeInTheDocument()
    expect(screen.queryByText('Brass')).not.toBeInTheDocument()
    await userEvent.clear(screen.getByLabelText('Players'))
    await userEvent.type(screen.getByLabelText('Players'), '1')
    expect(screen.queryByText('Brass')).not.toBeInTheDocument()
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

  it('searches BGG and adds a game without leaving the page', async () => {
    const wingspan = game(266192, 'Wingspan')
    let mine: UserGame[] = [rows[0]]
    let searched: string | null = null
    const saved: UserGameUpdate[] = []
    mockApi({
      'GET /api/me/games': () => Response.json(mine),
      'POST /api/me/games/fill-details': () => Response.json({ filled: 0, remaining: 0 }),
      'GET /api/games/search': (request) => {
        searched = new URL(request.url).searchParams.get('q')
        return Response.json([wingspan])
      },
      'PUT /api/me/games/266192': async (request) => {
        const body = (await request.json()) as UserGameUpdate
        saved.push(body)
        const added = { ...blankUserGame(wingspan), ...body } as UserGame
        mine = [...mine, added]
        return Response.json(added)
      },
    })
    renderWithProviders(<CollectionPage />)

    expect(await screen.findByText('1 of 1 games')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/Add a game/), 'wingspan')
    await userEvent.click(await screen.findByRole('checkbox', { name: 'I own it' }))

    await waitFor(() => expect(saved).toEqual([{ ownership: 'owned' }]))
    expect(searched).toBe('wingspan')
    // In the results and, straight away, in your list.
    expect(await screen.findByText('2 of 2 games')).toBeInTheDocument()
    expect(screen.getAllByText('Wingspan')).toHaveLength(2)

    await userEvent.click(screen.getByRole('button', { name: 'Clear search' }))
    expect(screen.getByLabelText(/Add a game/)).toHaveValue('')
    expect(screen.queryByRole('checkbox', { name: 'I own it' })).not.toBeInTheDocument()
  })

  it('shows a few results at first, and the rest on request', async () => {
    const found = Array.from({ length: 7 }, (_, i) => game(100 + i, `Ticket ${i + 1}`))
    mockApi({
      'GET /api/me/games': () => Response.json([]),
      'GET /api/games/search': () => Response.json(found),
    })
    renderWithProviders(<CollectionPage />)

    await userEvent.type(await screen.findByLabelText(/Add a game/), 'ticket')

    expect(await screen.findByText('Ticket 5')).toBeInTheDocument()
    expect(screen.queryByText('Ticket 6')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Show all 7 results' }))
    expect(screen.getByText('Ticket 7')).toBeInTheDocument()
  })

  it('offers to search BGG when the name filter finds nothing you have', async () => {
    let searched: string | null = null
    mockApi({
      'GET /api/me/games': () => Response.json(rows),
      'POST /api/me/games/fill-details': () => Response.json({ filled: 0, remaining: 0 }),
      'GET /api/games/search': (request) => {
        searched = new URL(request.url).searchParams.get('q')
        return Response.json([game(266192, 'Wingspan')])
      },
    })
    renderWithProviders(<CollectionPage />)

    await userEvent.type(await screen.findByLabelText('Name'), 'Wingspan')
    await userEvent.click(
      screen.getByRole('button', { name: 'Search BoardGameGeek for “Wingspan”' }),
    )

    expect(screen.getByLabelText(/Add a game/)).toHaveValue('Wingspan')
    expect(await screen.findByRole('checkbox', { name: 'I own it' })).toBeInTheDocument()
    expect(searched).toBe('Wingspan')
  })
})
