import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import type { UserGame, UserGameUpdate } from '../api/collection'
import type { GameSummary } from '../api/games'
import { blankUserGame } from '../components/userGameFields'
import { mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { GamesPage } from './GamesPage'

const wingspan: GameSummary = {
  id: 266192,
  name: 'Wingspan',
  year_published: 2019,
  is_expansion: false,
  thumbnail_url: null,
  min_players: 1,
  max_players: 5,
  min_playtime: 40,
  max_playtime: 70,
  weight: 2.48,
  bgg_rating: 8.0,
  bgg_rank: 38,
  best_with: [3],
  base_game_ids: [],
}

const expansion: GameSummary = {
  ...wingspan,
  id: 290448,
  name: 'Wingspan: European Expansion',
  is_expansion: true,
  best_with: [],
  base_game_ids: [266192],
}

describe('GamesPage', () => {
  beforeEach(() => {
    signIn()
  })

  it('searches BGG and shows what each game is like', async () => {
    let searched: string | null = null
    mockApi({
      'GET /api/games/search': (request) => {
        searched = new URL(request.url).searchParams.get('q')
        return Response.json([wingspan, expansion])
      },
    })
    renderWithProviders(<GamesPage />)

    await userEvent.type(screen.getByLabelText('Search BoardGameGeek'), 'wingspan')

    expect(await screen.findByText('Wingspan')).toBeInTheDocument()
    expect(searched).toBe('wingspan')
    expect(screen.getAllByText('1–5 players · 40–70 min · Weight 2.5/5')).toHaveLength(2)
    expect(screen.getByText('Best at 3')).toBeInTheDocument()
    expect(screen.getByText('Expansion')).toBeInTheDocument()
    expect(screen.getByText('Wingspan').closest('a')).toHaveAttribute('href', '/games/266192')
  })

  it('marks a result as owned, wished for or wanted with one tap', async () => {
    let rows: UserGame[] = [{ ...blankUserGame(expansion), want_to_play: true }]
    const saved: UserGameUpdate[] = []
    mockApi({
      'GET /api/games/search': () => Response.json([wingspan, expansion]),
      'GET /api/me/games': () => Response.json(rows),
      'PUT /api/me/games/266192': async (request) => {
        const body = (await request.json()) as UserGameUpdate
        saved.push(body)
        const row = { ...blankUserGame(wingspan), ...body } as UserGame
        rows = [...rows, row]
        return Response.json(row)
      },
    })
    renderWithProviders(<GamesPage />, { route: '/games?q=wingspan' })

    const [base, exp] = await screen.findAllByRole('checkbox', { name: 'Want to play' })
    expect(base).not.toBeChecked()
    expect(exp).toBeChecked()

    const [own] = screen.getAllByRole('checkbox', { name: 'I own it' })
    await userEvent.click(own)

    expect(own).toBeChecked()
    await waitFor(() => expect(saved).toEqual([{ ownership: 'owned' }]))
  })

  it('says so when nothing matches', async () => {
    mockApi({ 'GET /api/games/search': () => Response.json([]) })
    renderWithProviders(<GamesPage />)

    await userEvent.type(screen.getByLabelText('Search BoardGameGeek'), 'zzzz')

    expect(await screen.findByText('No games found for “zzzz”.')).toBeInTheDocument()
  })
})
