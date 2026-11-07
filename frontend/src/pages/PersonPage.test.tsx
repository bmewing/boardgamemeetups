import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'

import type { PersonProfile, SharedGame } from '../api/friends'
import { blankUserGame } from '../components/userGameFields'
import { mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { PersonPage } from './PersonPage'

const BEN_ID = '0190f0e2-0000-7000-8000-000000000002'
const ben = { id: BEN_ID, display_name: 'Ben', avatar_url: null, piece: null, piece_color: null }

function shared(id: number, name: string, changes: Partial<SharedGame>): SharedGame {
  const {
    notes: _notes,
    source: _source,
    updated_at: _updated,
    ...row
  } = blankUserGame({
    id,
    name,
    year_published: 2020,
    is_expansion: false,
    thumbnail_url: null,
    min_players: 2,
    max_players: 4,
    min_playtime: 30,
    max_playtime: 60,
    weight: 2,
    bgg_rating: 7,
    bgg_rank: 100,
    best_with: [],
    base_game_ids: [],
  })
  return { ...row, ...changes }
}

function renderPerson(profile: PersonProfile, games: SharedGame[] = []) {
  mockApi({
    [`GET /api/people/${BEN_ID}`]: () => Response.json(profile),
    [`GET /api/people/${BEN_ID}/games`]: () => Response.json(games),
  })
  renderWithProviders(
    <Routes>
      <Route path="/people/:userId" element={<PersonPage />} />
    </Routes>,
    { route: `/people/${BEN_ID}` },
  )
}

describe('PersonPage', () => {
  beforeEach(() => {
    signIn()
  })

  it("shows a friend's owned games, then their wishlist", async () => {
    renderPerson({ person: ben, relation: 'friends', games_visible: true }, [
      shared(1, 'Azul', { ownership: 'owned', rating: 8, can_teach: true, teach_minutes: 10 }),
      shared(2, 'Brass', { wishlist_priority: 1 }),
    ])

    expect(await screen.findByText('Azul')).toBeInTheDocument()
    expect(screen.getByText('Rated 8')).toBeInTheDocument()
    expect(screen.getByText('Can teach (10 min)')).toBeInTheDocument()
    expect(screen.queryByText('Brass')).not.toBeInTheDocument()

    await userEvent.click(screen.getByText('Wishlist & want to play'))

    expect(await screen.findByText('Brass')).toBeInTheDocument()
    expect(screen.getByText('Wishlist: Must have')).toBeInTheDocument()
  })

  it("says so when their games aren't shared with you", async () => {
    renderPerson({ person: ben, relation: 'outgoing', games_visible: false })

    expect(await screen.findByText("Ben doesn't share their games with you.")).toBeInTheDocument()
    expect(screen.getByText('Request sent')).toBeInTheDocument()
  })

  it("sends a friend request to someone you aren't friends with", async () => {
    let profile: PersonProfile = { person: ben, relation: 'none', games_visible: false }
    let sent: unknown
    mockApi({
      [`GET /api/people/${BEN_ID}`]: () => Response.json(profile),
      'POST /api/friends/requests': async (request) => {
        sent = await request.json()
        profile = { ...profile, relation: 'outgoing' }
        return Response.json({ person: ben, relation: 'outgoing' })
      },
    })
    renderWithProviders(
      <Routes>
        <Route path="/people/:userId" element={<PersonPage />} />
      </Routes>,
      { route: `/people/${BEN_ID}` },
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Add friend' }))

    expect(await screen.findByText('Request sent')).toBeInTheDocument()
    expect(sent).toEqual({ user_id: BEN_ID })
    expect(screen.queryByRole('button', { name: 'Add friend' })).not.toBeInTheDocument()
  })

  it('offers no friend request to a friend', async () => {
    renderPerson({ person: ben, relation: 'friends', games_visible: true })

    expect(await screen.findByText('Friends')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add friend' })).not.toBeInTheDocument()
  })
})
