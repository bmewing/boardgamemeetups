import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'

import type { UserGame, UserGameUpdate } from '../api/collection'
import type { GameDetail } from '../api/games'
import { blankUserGame } from '../components/userGameFields'
import { mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { GamePage } from './GamePage'

const azul: GameDetail = {
  id: 230802,
  name: 'Azul',
  year_published: 2017,
  is_expansion: false,
  thumbnail_url: null,
  image_url: null,
  min_players: 2,
  max_players: 4,
  min_playtime: 30,
  max_playtime: 45,
  playing_time: 45,
  min_age: 8,
  weight: 1.8,
  bgg_rating: 7.7,
  bgg_users_rated: 100,
  bgg_rank: 80,
  best_with: [2],
  recommended_with: [2, 3, 4],
  base_game_ids: [],
  categories: [],
  mechanics: [],
  player_count_votes: [],
  bgg_url: 'https://boardgamegeek.com/boardgame/230802',
}

/** A fake API for one game, not in the list at first; returns every PUT body, in order. */
function serve(start: UserGame[] = []) {
  let rows = start
  const saved: UserGameUpdate[] = []
  mockApi({
    'GET /api/games/230802': () => Response.json(azul),
    'GET /api/me/games': () => Response.json(rows),
    'GET /api/moods': () => Response.json([]),
    'PUT /api/me/games/230802': async (request) => {
      const body = (await request.json()) as UserGameUpdate
      saved.push(body)
      const row = { ...(rows[0] ?? blankUserGame(azul)), ...body } as UserGame
      rows = [row]
      return Response.json(row)
    },
  })
  return saved
}

function renderPage() {
  renderWithProviders(
    <Routes>
      <Route path="/games/:gameId" element={<GamePage />} />
    </Routes>,
    { route: '/games/230802' },
  )
}

describe('GamePage', () => {
  beforeEach(() => {
    signIn()
  })

  it('adds a game to your list with its first answer', async () => {
    const saved = serve()
    renderPage()

    expect(await screen.findByText('Not in your games yet. Any answer below adds it.'))
    await userEvent.click(screen.getByPlaceholderText("Don't own it"))
    await userEvent.click(await screen.findByRole('option', { name: 'Owned' }))

    await waitFor(() => expect(saved).toEqual([{ ownership: 'owned' }]))
    expect(screen.queryByText(/Not in your games yet/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Remove/ })).toBeInTheDocument()
  })

  it('edits wishlist priority, plays and notes, and marks BGG’s best count', async () => {
    const saved = serve([blankUserGame(azul)])
    renderPage()

    expect(await screen.findByRole('button', { name: "2 players: no answer (BGG's best)" }))
    expect(screen.getByRole('button', { name: '3 players: no answer' })).toBeInTheDocument()
    expect(screen.getByPlaceholderText('BGG 7.7')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('30–45 min')).toBeInTheDocument()

    await userEvent.click(screen.getByPlaceholderText('Not on it'))
    await userEvent.click(await screen.findByRole('option', { name: '1 · Must have' }))
    const plays = screen.getByRole('textbox', { name: 'Plays' })
    await userEvent.clear(plays)
    await userEvent.type(plays, '4')
    await userEvent.type(screen.getByRole('textbox', { name: 'Notes' }), '  Sleeved.  ')
    await userEvent.tab()

    await waitFor(() =>
      expect(saved).toEqual([{ wishlist_priority: 1 }, { plays: 4 }, { notes: 'Sleeved.' }]),
    )
  })
})
