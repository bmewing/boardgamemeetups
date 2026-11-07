import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { GroupSummary, MeetupBrief } from '../api/groups'
import { profile } from '../test/fixtures'
import { mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { Dashboard } from './Dashboard'

const brief = (over: Partial<MeetupBrief> = {}): MeetupBrief => ({
  id: 'm1',
  local_date: '2026-11-08',
  local_time: '15:00:00',
  starts_at: '2026-11-08T20:00:00Z',
  duration_minutes: 180,
  location: "Mark and Ames' place",
  status: 'scheduled',
  scheduled: true,
  edited: false,
  yes: 2,
  maybe: 1,
  no: 0,
  headcount: 3,
  going: [],
  my_response: null,
  ...over,
})

const group = (over: Partial<GroupSummary> = {}): GroupSummary => ({
  id: 'g1',
  name: 'Sunday Save the World',
  description: null,
  my_role: 'owner',
  member_count: 2,
  next_meetup: brief(),
  ...over,
})

const ownedGame = {
  game: {
    id: 13,
    name: 'Catan',
    year_published: 1995,
    is_expansion: false,
    thumbnail_url: 'https://example.com/catan.jpg',
    min_players: 3,
    max_players: 4,
    min_playtime: 60,
    max_playtime: 120,
    weight: 2.3,
    bgg_rating: 7.1,
    bgg_rank: 500,
    best_with: [4],
    base_game_ids: [],
  },
  ownership: 'owned',
  wishlist_priority: null,
  want_to_play: true,
  rating: 8,
  weight_vote: null,
  playtime_feel: null,
  can_teach: true,
  teach_minutes: null,
  plays: 4,
  will_bring: true,
  notes: null,
  player_counts: [],
  moods: [],
  source: 'manual',
  updated_at: '2026-11-04T00:00:00Z',
}

function setUp({
  groups = [group()],
  invites = [] as unknown[],
  games = [ownedGame] as unknown[],
  incoming = [] as unknown[],
} = {}) {
  signIn()
  mockApi({
    'GET /api/me': () => Response.json(profile),
    'GET /api/groups': () => Response.json({ groups, invites }),
    'GET /api/me/games': () => Response.json(games),
    'GET /api/friends': () => Response.json({ friends: [], incoming, outgoing: [] }),
  })
  renderWithProviders(<Dashboard />)
}

describe('Dashboard', () => {
  it('shows the next game night as a ticket to the date', async () => {
    setUp({
      groups: [
        group({
          id: 'g2',
          name: 'Later group',
          next_meetup: brief({ id: 'm2', starts_at: '2026-11-20T20:00:00Z' }),
        }),
        group(),
      ],
    })

    const ticket = await screen.findByRole('link', { name: /Next game night/ })
    expect(ticket).toHaveAttribute('href', '/meetups/m1')
    expect(within(ticket).getByText('Sunday Save the World')).toBeInTheDocument()
    expect(within(ticket).getByLabelText('3 people going')).toBeInTheDocument()
    expect(within(ticket).getByText('Are you coming? Tap to answer')).toBeInTheDocument()
  })

  it('shows your answer once you have given one', async () => {
    setUp({ groups: [group({ next_meetup: brief({ my_response: 'yes' }) })] })

    expect(await screen.findByText("You're going")).toBeInTheDocument()
    expect(screen.queryByText('Waiting on you')).not.toBeInTheDocument()
  })

  it('lists what is waiting on you', async () => {
    setUp({
      invites: [
        {
          id: 'i1',
          group_id: 'g9',
          group_name: 'Board Gamers',
          group_description: null,
          member_count: 3,
          invited_by: {
            id: 'u2',
            display_name: 'Ben',
            avatar_url: null,
            piece: null,
            piece_color: null,
          },
          created_at: '2026-11-04T00:00:00Z',
        },
      ],
      incoming: [
        { id: 'u3', display_name: 'Cy', avatar_url: null, piece: null, piece_color: null },
      ],
    })

    expect(await screen.findByText('Waiting on you')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Join Board Gamers\?/ })).toHaveAttribute(
      'href',
      '/groups',
    )
    expect(screen.getByRole('link', { name: /Coming to Sunday Save the World\?/ })).toHaveAttribute(
      'href',
      '/meetups/m1',
    )
    expect(screen.getByRole('link', { name: /1 friend request/ })).toHaveAttribute(
      'href',
      '/friends',
    )
  })

  it('leaves cancelled dates out', async () => {
    setUp({ groups: [group({ next_meetup: brief({ status: 'cancelled' }) })] })

    expect(await screen.findByText('Nothing on the calendar yet')).toBeInTheDocument()
    expect(screen.getByText('No dates coming up')).toBeInTheDocument()
  })

  it('invites someone with no groups to start one', async () => {
    setUp({ groups: [] })

    expect(await screen.findByText('Start your first group')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Start a group' })).toHaveAttribute('href', '/groups')
  })

  it('sums up your shelf', async () => {
    setUp()

    expect(await screen.findByText('plays logged')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Catan' })).toHaveAttribute('href', '/games/13')
  })

  it('points an empty shelf at the imports', async () => {
    setUp({ games: [] })

    expect(await screen.findByRole('link', { name: 'Pull from BGG' })).toHaveAttribute(
      'href',
      '/collection/pull',
    )
    expect(screen.getByRole('link', { name: 'Import a file' })).toHaveAttribute(
      'href',
      '/collection/import',
    )
  })
})
