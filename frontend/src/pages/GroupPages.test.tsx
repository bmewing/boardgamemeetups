import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'

import type { Group, GroupGame, Groups, Meetup, MeetupBrief, MeetupGames } from '../api/groups'
import { profile } from '../test/fixtures'
import { mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { GroupPage } from './GroupPage'
import { GroupsPage } from './GroupsPage'
import { MeetupPage } from './MeetupPage'

const GROUP_ID = '0190f0e2-0000-7000-8000-0000000000a1'
const MEETUP_ID = '0190f0e2-0000-7000-8000-0000000000b1'
const ann = {
  id: profile.id,
  display_name: 'Sam',
  avatar_url: null,
  piece: null,
  piece_color: null,
}
const ben = {
  id: '0190f0e2-0000-7000-8000-000000000002',
  display_name: 'Ben',
  avatar_url: null,
  piece: null,
  piece_color: null,
}

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
  headcount: 1,
  going: [],
  my_response: null,
}

const group: Group = {
  id: GROUP_ID,
  name: 'Thursday Crew',
  description: null,
  kind: 'board_games',
  rpg_system: null,
  time_zone: 'UTC',
  willing_to_split: false,
  schedule: { kind: 'weekly', every_weeks: 1, weekday: 3, starts_on: '2026-11-05' },
  start_time: '19:00:00',
  duration_minutes: 180,
  location: "Sam's place",
  plus_one_limit: 0,
  my_role: 'owner',
  members: [
    { person: ann, role: 'owner', is_gm: false, joined_at: '2026-11-01T00:00:00Z' },
    { person: ben, role: 'member', is_gm: false, joined_at: '2026-11-02T00:00:00Z' },
  ],
  invites: [],
  upcoming: [
    brief,
    { ...brief, id: 'm2', local_date: '2026-11-12', yes: 0, headcount: 0, edited: true },
  ],
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
          group_kind: 'board_games',
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
              kind: 'board_games',
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
    expect(sent).toMatchObject({
      name: 'Thursday Crew',
      time_zone: 'America/Chicago',
      plus_one_limit: 0, // no guests unless you say so
    })
  })

  it('asks how many guests each member can bring', async () => {
    let sent: unknown
    mockApi({
      'GET /api/me': () => Response.json(profile),
      'GET /api/groups': () => Response.json({ groups: [], invites: [] }),
      'POST /api/groups': async (request) => {
        sent = await request.json()
        return Response.json({ ...group, plus_one_limit: 2 }, { status: 201 })
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
    const guests = screen.getByRole('textbox', { name: 'Guests each member can bring' })
    await userEvent.clear(guests)
    await userEvent.type(guests, '2')
    await userEvent.click(screen.getByRole('button', { name: 'Make the group' }))

    expect(await screen.findByText('Group page')).toBeInTheDocument()
    expect(sent).toMatchObject({ name: 'Thursday Crew', plus_one_limit: 2 })
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

  it("filters the group's games by what members' expansions let them seat", async () => {
    const summary = (id: number, name: string, min: number, max: number) => ({
      id,
      name,
      year_published: 2020,
      is_expansion: false,
      thumbnail_url: null,
      min_players: min,
      max_players: max,
      min_playtime: 30,
      max_playtime: 45,
      weight: 2,
      bgg_rating: null,
      bgg_rank: null,
      best_with: [],
      base_game_ids: [],
      is_custom: false,
    })
    const rollup = {
      rating: null,
      rated_by: 0,
      lowest_rating: null,
      weight: null,
      best_at: [],
      length_minutes: null,
      teach_minutes: null,
      teachers: [],
      new_to_it: [],
      moods: [],
      want_to_play: [],
      wishlist: [],
    }
    const library: GroupGame[] = [
      {
        game: summary(1, 'Azul', 2, 4),
        owners: [ann],
        expansions: [
          {
            id: 3,
            name: 'Azul: Big Box',
            year_published: 2021,
            thumbnail_url: null,
            is_expansion: true,
          },
        ],
        min_players: 2,
        max_players: 6,
        answers: [],
        rollup,
      },
      {
        game: summary(2, 'Brass', 3, 4),
        owners: [ben],
        expansions: [],
        min_players: 3,
        max_players: 4,
        answers: [],
        rollup,
      },
    ]
    renderGroup(group, {
      [`GET /api/groups/${GROUP_ID}/games`]: () => Response.json(library),
      'GET /api/moods': () => Response.json([]),
    })

    await userEvent.click(await screen.findByRole('tab', { name: 'Games' }))
    expect(await screen.findByText('With Azul: Big Box (seats 2–6)')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/Players/), '6')
    expect(screen.getByText('Azul')).toBeInTheDocument()
    expect(screen.queryByText('Brass')).not.toBeInTheDocument()
  })

  it("offers to add members you aren't friends with", async () => {
    const cat = {
      id: '0190f0e2-0000-7000-8000-000000000003',
      display_name: 'Cat',
      avatar_url: null,
      piece: null,
      piece_color: null,
    }
    const dee = {
      id: '0190f0e2-0000-7000-8000-000000000004',
      display_name: 'Dee',
      avatar_url: null,
      piece: null,
      piece_color: null,
    }
    let outgoing: { person: typeof ben; since: string }[] = []
    let sent: unknown
    renderGroup(
      {
        ...group,
        members: [
          ...group.members,
          { person: cat, role: 'member', is_gm: false, joined_at: '2026-11-02T00:00:00Z' },
          { person: dee, role: 'member', is_gm: false, joined_at: '2026-11-02T00:00:00Z' },
        ],
      },
      {
        'GET /api/friends': () =>
          Response.json({
            friends: [{ person: cat, since: '2026-11-01T00:00:00Z' }],
            incoming: [{ person: dee, since: '2026-11-01T00:00:00Z' }],
            outgoing,
          }),
        'GET /api/blocks': () => Response.json([]),
        'POST /api/friends/requests': async (request) => {
          sent = await request.json()
          outgoing = [{ person: ben, since: '2026-11-06T00:00:00Z' }]
          return Response.json({ person: ben, relation: 'outgoing' })
        },
      },
    )

    await userEvent.click(await screen.findByRole('tab', { name: /Members/ }))
    const add = await screen.findByRole('button', { name: 'Add Ben as a friend' })
    expect(screen.getAllByRole('button', { name: /as a friend/ })).toHaveLength(1)
    expect(screen.getByRole('button', { name: "Accept Dee's friend request" })).toBeInTheDocument()

    await userEvent.click(add)

    expect(await screen.findByText('Request sent')).toBeInTheDocument()
    expect(sent).toEqual({ user_id: ben.id })
  })

  it('invites someone picked from the suggestions, and marks members', async () => {
    let sent: unknown
    const cat = {
      id: '0190f0e2-0000-7000-8000-000000000003',
      display_name: 'Cat',
      avatar_url: null,
      piece: null,
      piece_color: null,
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

  it("offers your friends who aren't in the group before you type", async () => {
    let sent: unknown
    const cat = {
      id: '0190f0e2-0000-7000-8000-000000000003',
      display_name: 'Cat',
      avatar_url: null,
      piece: null,
      piece_color: null,
    }
    const dee = {
      id: '0190f0e2-0000-7000-8000-000000000004',
      display_name: 'Dee',
      avatar_url: null,
      piece: null,
      piece_color: null,
    }
    const since = '2026-11-01T00:00:00Z'
    renderGroup(group, {
      'GET /api/friends': () =>
        Response.json({
          friends: [
            { person: ben, since },
            { person: cat, since },
            { person: dee, since },
          ],
          incoming: [],
          outgoing: [],
        }),
      'GET /api/blocks': () => Response.json([]),
      [`POST /api/groups/${GROUP_ID}/invites`]: async (request) => {
        sent = await request.json()
        return Response.json(
          {
            invite: { id: 'i1', person: dee, email: null, invited_by: ann, created_at: since },
            on_app: true,
          },
          { status: 201 },
        )
      },
    })

    await userEvent.click(await screen.findByRole('tab', { name: /Members/ }))
    await userEvent.click(screen.getByLabelText(/Invite someone/))

    expect(await screen.findByRole('option', { name: /Cat/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Dee/ })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /Ben/ })).not.toBeInTheDocument() // a member

    await userEvent.type(screen.getByLabelText(/Invite someone/), 'd')
    await waitFor(() =>
      expect(screen.queryByRole('option', { name: /Cat/ })).not.toBeInTheDocument(),
    )
    await userEvent.click(screen.getByRole('option', { name: /Dee/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Invite' }))

    expect(await screen.findByText(/Invited Dee/)).toBeInTheDocument()
    expect(sent).toEqual({ user_id: dee.id })
  })
})

describe('MeetupPage', () => {
  beforeEach(() => signIn())

  const meetup: Meetup = {
    ...brief,
    notes: 'Bring snacks',
    recap: null,
    recap_updated_at: null,
    previous_recap: null,
    group: {
      id: GROUP_ID,
      name: 'Thursday Crew',
      kind: 'board_games',
      time_zone: 'UTC',
      willing_to_split: true,
      plus_one_limit: 0,
    },
    my_role: 'member',
    rsvps: [{ person: ben, response: 'yes', guests: 0, moods: ['chill'] }],
    no_answer: [ann],
    my_guests: 0,
    my_moods: [],
  }
  const moods = [
    { id: 'chill', name: 'Chill', description: 'Relaxed', taggable: true },
    { id: 'brain', name: 'Brain-burner', description: 'Heavy', taggable: true },
    { id: 'no_preference', name: 'No preference', description: 'Anything', taggable: false },
  ]
  const rollup = {
    rating: null,
    rated_by: 0,
    lowest_rating: null,
    weight: null,
    best_at: [],
    length_minutes: 50,
    teach_minutes: 10,
    teachers: [ben],
    new_to_it: [ann],
    moods: [],
    want_to_play: [],
    wishlist: [],
  }
  const games: MeetupGames = {
    confirmed: 5,
    players: 5,
    guests: 0,
    maybes: 0,
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
          is_custom: false,
        },
        bringers: [ben],
        fit: 'split',
        min_players: 2,
        max_players: 4,
        expansions: [],
        rollup,
        score: 4.5,
        reasons: [
          { text: 'Sam wants to play', tone: 'good' },
          { text: 'Ben can teach (10 min)', tone: 'info' },
        ],
      },
    ],
  }

  it('saves your answer and lists games that fit', async () => {
    let answered: unknown
    mockApi({
      [`GET /api/meetups/${MEETUP_ID}`]: () => Response.json(meetup),
      [`GET /api/meetups/${MEETUP_ID}/games`]: () => Response.json(games),
      'GET /api/moods': () => Response.json(moods),
      [`PUT /api/meetups/${MEETUP_ID}/rsvp`]: async (request) => {
        answered = await request.json()
        return Response.json({
          ...meetup,
          yes: 2,
          my_response: 'yes',
          rsvps: [...meetup.rsvps, { person: ann, response: 'yes', guests: 0, moods: [] }],
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
    expect(screen.getByText('Sam wants to play')).toBeInTheDocument()
    expect(screen.getByText('About 50 min, plus 10 to teach')).toBeInTheDocument()
    expect(screen.getByText(/1 game left out/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByText('Going'))

    await waitFor(() => expect(answered).toEqual({ response: 'yes', guests: 0, moods: [] }))
    expect(await screen.findByText('Going (2)')).toBeInTheDocument()
    // Guests are off in this group; moods show once you might come.
    expect(screen.queryByText('Bringing anyone?')).not.toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Chill' })).toBeInTheDocument()
  })

  it('lets you try another player count and a time limit, just for you', async () => {
    const asked: (string | null)[] = []
    const quick = {
      ...games.games[0],
      game: { ...games.games[0].game, id: 2, name: 'Hive' },
      fit: 'together' as const,
      rollup: { ...rollup, length_minutes: 20, teach_minutes: null },
    }
    mockApi({
      [`GET /api/meetups/${MEETUP_ID}`]: () => Response.json(meetup),
      [`GET /api/meetups/${MEETUP_ID}/games`]: (request) => {
        const players = new URL(request.url).searchParams.get('players')
        asked.push(players)
        return Response.json(
          players === null
            ? games
            : { ...games, players: Number(players), games: [...games.games, quick] },
        )
      },
      'GET /api/moods': () => Response.json(moods),
    })
    renderWithProviders(
      <Routes>
        <Route path="/meetups/:meetupId" element={<MeetupPage />} />
      </Routes>,
      { route: `/meetups/${MEETUP_ID}` },
    )

    expect(await screen.findByText('Azul')).toBeInTheDocument()
    expect(screen.queryByText(/Filtered just for you/)).not.toBeInTheDocument()

    await userEvent.type(screen.getByRole('textbox', { name: 'Players' }), '7')
    expect(await screen.findByText('Hive')).toBeInTheDocument()
    expect(asked).toContain('7')
    expect(screen.getByText(/for 7 players \(5 going\)/)).toBeInTheDocument()
    expect(screen.getByText(/Filtered just for you: fitted to 7 players\./)).toBeInTheDocument()

    // Azul takes about an hour with teaching; Hive about 20 minutes.
    await userEvent.type(screen.getByRole('textbox', { name: 'Longest game' }), '45')
    expect(await screen.findByText(/45 min or less \(1 longer game hidden\)/)).toBeInTheDocument()
    expect(screen.queryByText('Azul')).not.toBeInTheDocument()
    expect(screen.getByText('Hive')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: "Back to who's going" }))
    expect(await screen.findByText('Azul')).toBeInTheDocument()
    expect(screen.queryByText('Hive')).not.toBeInTheDocument()
    expect(screen.queryByText(/Filtered just for you/)).not.toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Players' })).toHaveValue('')
  })

  it('shows the top 10 games until you ask for all of them', async () => {
    const many: MeetupGames = {
      ...games,
      games: Array.from({ length: 12 }, (_, i) => ({
        ...games.games[0],
        game: { ...games.games[0].game, id: i + 1, name: `Game ${i + 1}` },
        score: 12 - i,
      })),
    }
    mockApi({
      [`GET /api/meetups/${MEETUP_ID}`]: () => Response.json(meetup),
      [`GET /api/meetups/${MEETUP_ID}/games`]: () => Response.json(many),
      'GET /api/moods': () => Response.json(moods),
    })
    renderWithProviders(
      <Routes>
        <Route path="/meetups/:meetupId" element={<MeetupPage />} />
      </Routes>,
      { route: `/meetups/${MEETUP_ID}` },
    )

    expect(await screen.findByText('Game 10')).toBeInTheDocument()
    expect(screen.queryByText('Game 11')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Show all 12' }))
    expect(screen.getByText('Game 12')).toBeInTheDocument()
  })

  it('brings guests and picks moods, with No preference on its own', async () => {
    const sent: unknown[] = []
    let current: Meetup = {
      ...meetup,
      group: { ...meetup.group, plus_one_limit: 2 },
      my_response: 'yes',
      rsvps: [...meetup.rsvps, { person: ann, response: 'yes', guests: 0, moods: [] }],
      no_answer: [],
    }
    mockApi({
      [`GET /api/meetups/${MEETUP_ID}`]: () => Response.json(current),
      [`GET /api/meetups/${MEETUP_ID}/games`]: () => Response.json(games),
      'GET /api/moods': () => Response.json(moods),
      [`PUT /api/meetups/${MEETUP_ID}/rsvp`]: async (request) => {
        const body = (await request.json()) as { guests: number; moods: string[] }
        sent.push(body)
        current = {
          ...current,
          my_guests: body.guests,
          my_moods: body.moods,
          rsvps: [
            meetup.rsvps[0],
            { person: ann, response: 'yes', guests: body.guests, moods: body.moods },
          ],
        }
        return Response.json(current)
      },
    })
    renderWithProviders(
      <Routes>
        <Route path="/meetups/:meetupId" element={<MeetupPage />} />
      </Routes>,
      { route: `/meetups/${MEETUP_ID}` },
    )

    await userEvent.click((await screen.findAllByLabelText('Bringing anyone?'))[0])
    await userEvent.click(await screen.findByRole('option', { name: 'Me + 1' }))
    await waitFor(() => expect(sent).toHaveLength(1))
    expect(await screen.findByText('Going (2 + 1 guest)')).toBeInTheDocument()
    expect(screen.getByText('Sam +1')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('checkbox', { name: 'Brain-burner' }))
    await waitFor(() => expect(sent).toHaveLength(2))
    await userEvent.click(screen.getByRole('checkbox', { name: 'No preference' }))
    await waitFor(() => expect(sent).toHaveLength(3))

    expect(sent).toEqual([
      { response: 'yes', guests: 1, moods: [] },
      { response: 'yes', guests: 1, moods: ['brain'] },
      { response: 'yes', guests: 1, moods: ['no_preference'] },
    ])
    // Ben's Chill and Sam's No preference, from everyone who might come.
    expect(await screen.findByText('Chill · No preference', { exact: false })).toHaveTextContent(
      /^In the mood for: Chill · No preference$/,
    )
  })
})

describe('Calendar feed', () => {
  beforeEach(() => signIn())

  it('makes a link to subscribe to', async () => {
    let feed: { token: string; created_at: string } | null = null
    mockApi({
      'GET /api/groups': () =>
        Response.json({
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
        }),
      'GET /api/me/calendar-feed': () => Response.json(feed),
      'POST /api/me/calendar-feed': () => {
        feed = { token: 'secret-token', created_at: '2026-11-04T00:00:00Z' }
        return Response.json(feed, { status: 201 })
      },
    })
    renderWithProviders(<GroupsPage />)

    expect(await screen.findByText(/1 going/)).toBeInTheDocument()
    await userEvent.click(await screen.findByRole('button', { name: 'Get a calendar link' }))

    const link = await screen.findByLabelText('Calendar link')
    expect(link).toHaveValue(`${window.location.origin}/api/calendar/secret-token.ics`)
    expect(screen.getByRole('link', { name: 'Open in calendar app' })).toHaveAttribute(
      'href',
      expect.stringMatching(/^webcal:\/\/.*\/api\/calendar\/secret-token\.ics$/),
    )
  })
})
