import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'

import type { Group, Groups, Meetup, MeetupBrief, MeetupGames } from '../api/groups'
import { profile } from '../test/fixtures'
import { mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { GroupPage } from './GroupPage'
import { GroupsPage } from './GroupsPage'
import { MeetupPage } from './MeetupPage'

const GROUP_ID = '0190f0e2-0000-7000-8000-0000000000a1'
const MEETUP_ID = '0190f0e2-0000-7000-8000-0000000000b1'
const ann = { id: profile.id, display_name: 'Sam', avatar_url: null }
const ben = { id: '0190f0e2-0000-7000-8000-000000000002', display_name: 'Ben', avatar_url: null }

const brief: MeetupBrief = {
  id: MEETUP_ID,
  local_date: '2026-11-05',
  local_time: '19:00:00',
  starts_at: '2026-11-06T01:00:00Z',
  duration_minutes: 180,
  location: "Sam's place",
  status: 'scheduled',
  scheduled: true,
  edited: false,
  yes: 1,
  maybe: 0,
  no: 0,
  my_response: null,
}

const group: Group = {
  id: GROUP_ID,
  name: 'Thursday Crew',
  description: null,
  time_zone: 'UTC',
  willing_to_split: false,
  schedule: { kind: 'weekly', every_weeks: 1, weekday: 3, starts_on: '2026-11-05' },
  start_time: '19:00:00',
  duration_minutes: 180,
  location: "Sam's place",
  my_role: 'owner',
  members: [
    { person: ann, role: 'owner', joined_at: '2026-11-01T00:00:00Z' },
    { person: ben, role: 'member', joined_at: '2026-11-02T00:00:00Z' },
  ],
  invites: [],
  upcoming: [brief, { ...brief, id: 'm2', local_date: '2026-11-12', yes: 0, edited: true }],
  recent: [],
}

describe('GroupsPage', () => {
  beforeEach(() => signIn())

  it('lists your groups and lets you join one you were invited to', async () => {
    let groups: Groups = {
      groups: [],
      invites: [
        {
          id: 'inv1',
          group_id: GROUP_ID,
          group_name: 'Thursday Crew',
          group_description: null,
          member_count: 2,
          invited_by: ben,
          created_at: '2026-11-03T00:00:00Z',
        },
      ],
    }
    let joined = false
    mockApi({
      'GET /api/groups': () => Response.json(groups),
      'POST /api/group-invites/inv1/accept': () => {
        joined = true
        groups = {
          invites: [],
          groups: [
            {
              id: GROUP_ID,
              name: 'Thursday Crew',
              description: null,
              my_role: 'member',
              member_count: 3,
              next_meetup: brief,
            },
          ],
        }
        return Response.json({ ...group, my_role: 'member' })
      },
    })
    renderWithProviders(
      <Routes>
        <Route path="/" element={<GroupsPage />} />
        <Route path="/groups/:groupId" element={<p>Group page</p>} />
      </Routes>,
    )

    expect(await screen.findByText('Ben invited you · 2 members')).toBeInTheDocument()
    expect(screen.getByText(/never your notes/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Join' }))

    expect(await screen.findByText('Group page')).toBeInTheDocument()
    expect(joined).toBe(true)
  })

  it("starts a new group in your account's time zone", async () => {
    let sent: unknown
    mockApi({
      'GET /api/me': () => Response.json({ ...profile, time_zone: 'America/Chicago' }),
      'GET /api/groups': () => Response.json({ groups: [], invites: [] }),
      'POST /api/groups': async (request) => {
        sent = await request.json()
        return Response.json(group, { status: 201 })
      },
    })
    renderWithProviders(
      <Routes>
        <Route path="/" element={<GroupsPage />} />
        <Route path="/groups/:groupId" element={<p>Group page</p>} />
      </Routes>,
    )

    await userEvent.click(await screen.findByRole('button', { name: 'New group' }))
    await userEvent.type(await screen.findByLabelText(/Name/), 'Thursday Crew')
    expect(await screen.findAllByDisplayValue('America/Chicago')).not.toHaveLength(0)
    await userEvent.click(screen.getByRole('button', { name: 'Make the group' }))

    expect(await screen.findByText('Group page')).toBeInTheDocument()
    expect(sent).toMatchObject({ name: 'Thursday Crew', time_zone: 'America/Chicago' })
  })
})

function renderGroup(data: Group, extra: Parameters<typeof mockApi>[0] = {}) {
  mockApi({
    'GET /api/me': () => Response.json(profile),
    [`GET /api/groups/${GROUP_ID}`]: () => Response.json(data),
    ...extra,
  })
  renderWithProviders(
    <Routes>
      <Route path="/groups/:groupId" element={<GroupPage />} />
    </Routes>,
    { route: `/groups/${GROUP_ID}` },
  )
}

describe('GroupPage', () => {
  beforeEach(() => signIn())

  it('shows the schedule and upcoming dates', async () => {
    renderGroup(group)

    expect(await screen.findByText('Every Thursday')).toBeInTheDocument()
    expect(screen.getByText(/1 going · Sam's place/)).toBeInTheDocument()
    expect(screen.getByText('Changed')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Settings' })).toBeInTheDocument()
  })

  it('hides settings from members', async () => {
    renderGroup({ ...group, my_role: 'member' })

    expect(await screen.findByText('Every Thursday')).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Settings' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add a date' })).not.toBeInTheDocument()
  })

  it('invites someone picked from the suggestions, and marks members', async () => {
    let sent: unknown
    const cat = {
      id: '0190f0e2-0000-7000-8000-000000000003',
      display_name: 'Cat',
      avatar_url: null,
    }
    renderGroup(group, {
      'GET /api/people/search': () =>
        Response.json([
          { person: ben, relation: 'friends' },
          { person: cat, relation: 'none' },
        ]),
      [`POST /api/groups/${GROUP_ID}/invites`]: async (request) => {
        sent = await request.json()
        return Response.json(
          {
            invite: {
              id: 'i1',
              person: cat,
              email: null,
              invited_by: ann,
              created_at: '2026-11-03T00:00:00Z',
            },
            on_app: true,
          },
          { status: 201 },
        )
      },
    })

    await userEvent.click(await screen.findByRole('tab', { name: /Members/ }))
    await userEvent.type(screen.getByLabelText(/Invite someone/), 'ca')

    expect(await screen.findByText('In group')).toBeInTheDocument() // Ben
    await userEvent.click(screen.getByRole('option', { name: /Cat/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Invite' }))

    expect(await screen.findByText(/Invited Cat/)).toBeInTheDocument()
    expect(sent).toEqual({ user_id: cat.id })
  })
})

describe('MeetupPage', () => {
  beforeEach(() => signIn())

  const meetup: Meetup = {
    ...brief,
    notes: 'Bring snacks',
    group: { id: GROUP_ID, name: 'Thursday Crew', time_zone: 'UTC', willing_to_split: true },
    my_role: 'member',
    rsvps: [{ person: ben, response: 'yes' }],
    no_answer: [ann],
  }
  const games: MeetupGames = {
    confirmed: 5,
    willing_to_split: true,
    unknown_player_count: 1,
    games: [
      {
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
          bgg_rating: 7.7,
          bgg_rank: 80,
          best_with: [2],
          base_game_ids: [],
        },
        bringers: [ben],
        fit: 'split',
      },
    ],
  }

  it('saves your answer and lists games that fit', async () => {
    let answered: unknown
    mockApi({
      [`GET /api/meetups/${MEETUP_ID}`]: () => Response.json(meetup),
      [`GET /api/meetups/${MEETUP_ID}/games`]: () => Response.json(games),
      [`PUT /api/meetups/${MEETUP_ID}/rsvp`]: async (request) => {
        answered = await request.json()
        return Response.json({
          ...meetup,
          yes: 2,
          my_response: 'yes',
          rsvps: [...meetup.rsvps, { person: ann, response: 'yes' }],
          no_answer: [],
        })
      },
    })
    renderWithProviders(
      <Routes>
        <Route path="/meetups/:meetupId" element={<MeetupPage />} />
      </Routes>,
      { route: `/meetups/${MEETUP_ID}` },
    )

    expect(await screen.findByText('Bring snacks')).toBeInTheDocument()
    expect(await screen.findByText('Azul')).toBeInTheDocument()
    expect(screen.getByText('One of several tables')).toBeInTheDocument()
    expect(screen.getByText(/1 game left out/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByText('Going'))

    await waitFor(() => expect(answered).toEqual({ response: 'yes' }))
    expect(await screen.findByText('Going (2)')).toBeInTheDocument()
  })
})
