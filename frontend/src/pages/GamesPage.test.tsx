import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import type { GameSummary } from '../api/games'
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

  it('says so when nothing matches', async () => {
    mockApi({ 'GET /api/games/search': () => Response.json([]) })
    renderWithProviders(<GamesPage />)

    await userEvent.type(screen.getByLabelText('Search BoardGameGeek'), 'zzzz')

    expect(await screen.findByText('No games found for “zzzz”.')).toBeInTheDocument()
  })
})
