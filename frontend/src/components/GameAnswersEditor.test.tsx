import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import type { Mood, UserGame, UserGameUpdate } from '../api/collection'
import { CollectionPage } from '../pages/CollectionPage'
import { mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'

const azul = (extra: Partial<UserGame> = {}): UserGame => ({
  game: {
    id: 1,
    name: 'Azul',
    year_published: 2017,
    is_expansion: false,
    thumbnail_url: null,
    min_players: 2,
    max_players: 4,
    min_playtime: 30,
    max_playtime: 45,
    weight: 1.8,
    bgg_rating: 7.8,
    bgg_rank: null,
    best_with: [2],
    base_game_ids: [],
    is_custom: false,
  },
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

const moods: Mood[] = [
  { id: 'chill', name: 'Chill', description: '', taggable: true },
  { id: 'something_new', name: 'Something new', description: '', taggable: false },
]

/** A fake API holding one game; returns every PUT body it was sent, in order. */
function serve(start: UserGame) {
  let current = start
  const saved: UserGameUpdate[] = []
  mockApi({
    'GET /api/me/games': () => Response.json([current]),
    'GET /api/moods': () => Response.json(moods),
    'POST /api/me/games/fill-details': () => Response.json({ filled: 0, remaining: 0 }),
    'PUT /api/me/games/1': async (request) => {
      const body = (await request.json()) as UserGameUpdate
      saved.push(body)
      current = { ...current, ...body } as UserGame
      return Response.json(current)
    },
  })
  return saved
}

describe('GameAnswersEditor on My games', () => {
  beforeEach(() => {
    signIn()
  })

  it('cycles a player count through best, recommended, not recommended and blank', async () => {
    const saved = serve(azul())
    renderWithProviders(<CollectionPage />)

    const three = await screen.findByRole('button', { name: '3 players: no answer' })
    await userEvent.click(three)
    expect(screen.getByRole('button', { name: '3 players: best' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '3 players: best' }))
    await userEvent.click(screen.getByRole('button', { name: '3 players: recommended' }))
    await userEvent.click(screen.getByRole('button', { name: '3 players: not recommended' }))

    await waitFor(() => expect(saved).toHaveLength(4))
    expect(saved.map((s) => s.player_counts)).toEqual([
      [{ players: 3, vote: 'best' }],
      [{ players: 3, vote: 'recommended' }],
      [{ players: 3, vote: 'not_recommended' }],
      [],
    ])
    expect(screen.getByRole('button', { name: '3 players: no answer' })).toBeInTheDocument()
  })

  it('shows BGG values as hints and saves a rating when you leave the box', async () => {
    const saved = serve(azul())
    renderWithProviders(<CollectionPage />)

    const rating = await screen.findByPlaceholderText('BGG 7.8')
    expect(screen.getByPlaceholderText('BGG 1.8')).toBeInTheDocument()
    await userEvent.type(rating, '7.5')
    expect(saved).toEqual([])
    await userEvent.tab()

    await waitFor(() => expect(saved).toEqual([{ rating: 7.5 }]))
  })

  it('asks for a teach time before saving "can teach"', async () => {
    const saved = serve(azul())
    renderWithProviders(<CollectionPage />)

    await userEvent.click(await screen.findByLabelText('Can teach'))
    expect(screen.getByText('How long?')).toBeInTheDocument()
    expect(saved).toEqual([])

    await userEvent.type(screen.getByLabelText('Teach time in minutes'), '15')
    await userEvent.tab()

    await waitFor(() => expect(saved).toEqual([{ can_teach: true, teach_minutes: 15 }]))
    expect(screen.queryByText('How long?')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Can teach')).toBeChecked()
  })

  it('counts owners as teachers until they untick it', async () => {
    const saved = serve(azul({ can_teach: null }))
    renderWithProviders(<CollectionPage />)

    const box = await screen.findByLabelText('Can teach')
    expect(box).toBeChecked()
    await userEvent.click(box)

    await waitFor(() => expect(saved).toEqual([{ can_teach: false }]))
    expect(screen.getByLabelText('Can teach')).not.toBeChecked()
  })

  it('offers only taggable moods, and "will bring" only for games you own', async () => {
    const saved = serve(azul({ ownership: null, want_to_play: true }))
    renderWithProviders(<CollectionPage />)
    await userEvent.click(await screen.findByRole('radio', { name: 'All' }))

    const card = (await screen.findByText('Azul')).closest('.mantine-Card-root') as HTMLElement
    expect(within(card).queryByLabelText('Will bring')).not.toBeInTheDocument()

    await userEvent.click(within(card).getByPlaceholderText('Moods'))
    expect(screen.queryByRole('option', { name: 'Something new' })).not.toBeInTheDocument()
    await userEvent.click(await screen.findByRole('option', { name: 'Chill' }))

    await waitFor(() => expect(saved).toEqual([{ moods: ['chill'] }]))
  })
})
