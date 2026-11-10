import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'

import type { GameSummary } from '../api/games'
import type { Meetup, MeetupGames } from '../api/groups'
import type { PlayLog, VoteState } from '../api/votes'
import { profile } from '../test/fixtures'
import { mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { MeetupPage } from './MeetupPage'

const MEETUP_ID = '0190f0e2-0000-7000-8000-0000000000c1'
const sam = {
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

const azul: GameSummary = {
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
}

function meetupAt(startsAt: string, role: Meetup['my_role'] = 'owner'): Meetup {
  return {
    id: MEETUP_ID,
    local_date: startsAt.slice(0, 10),
    local_time: '19:00:00',
    starts_at: startsAt,
    duration_minutes: 180,
    location: null,
    is_online: false,
    online_url: null,
    status: 'scheduled',
    scheduled: false,
    edited: false,
    yes: 2,
    maybe: 0,
    no: 0,
    headcount: 2,
    going: [],
    my_response: 'yes',
    notes: null,
    group: { id: 'g1', name: 'Crew', time_zone: 'UTC', willing_to_split: false, plus_one_limit: 0 },
    my_role: role,
    rsvps: [
      {
        person: ben,
        response: 'yes',
        guests: 0,
        moods: [],
        bga_username: null,
        bga_premium: false,
      },
      {
        person: sam,
        response: 'yes',
        guests: 0,
        moods: [],
        bga_username: null,
        bga_premium: false,
      },
    ],
    no_answer: [],
    my_guests: 0,
    my_moods: [],
  }
}

const noGames: MeetupGames = {
  confirmed: 2,
  players: 2,
  guests: 0,
  maybes: 0,
  willing_to_split: false,
  games: [],
  unknown_player_count: 0,
  online: false,
  premium_host_going: false,
}

const nomination = {
  id: 'n1',
  game: azul,
  nominated_by: ben,
  votes: [ben],
  my_vote: false,
  picked: false,
  fits_now: true,
  fit: 'together' as const,
  min_players: 2,
  max_players: 4,
  bring: null,
  bga: null,
  can_remove: false,
}

const openVote: VoteState = {
  locked: false,
  locked_at: null,
  can_vote: true,
  can_lock: true,
  headcount: 2,
  nominations: [nomination],
  nominatable: [],
  online: false,
  premium_host_going: false,
}

function renderMeetup(meetup: Meetup, routes: Parameters<typeof mockApi>[0]) {
  mockApi({
    'GET /api/me': () => Response.json(profile),
    'GET /api/moods': () => Response.json([]),
    [`GET /api/meetups/${MEETUP_ID}`]: () => Response.json(meetup),
    [`GET /api/meetups/${MEETUP_ID}/games`]: () => Response.json(noGames),
    ...routes,
  })
  renderWithProviders(
    <Routes>
      <Route path="/meetups/:meetupId" element={<MeetupPage />} />
    </Routes>,
    { route: `/meetups/${MEETUP_ID}` },
  )
}

describe('Voting on a date', () => {
  beforeEach(() => signIn())

  it('votes, locks the pick, and claims bringing it', async () => {
    let state = openVote
    const locked: string[][] = []
    renderMeetup(meetupAt('2099-01-01T19:00:00Z'), {
      [`GET /api/meetups/${MEETUP_ID}/vote`]: () => Response.json(state),
      [`PUT /api/meetups/${MEETUP_ID}/nominations/n1/vote`]: () => {
        state = { ...state, nominations: [{ ...nomination, votes: [ben, sam], my_vote: true }] }
        return Response.json(state)
      },
      [`POST /api/meetups/${MEETUP_ID}/lock`]: async (request) => {
        locked.push(((await request.json()) as { nomination_ids: string[] }).nomination_ids)
        state = {
          ...state,
          locked: true,
          can_vote: false,
          nominations: [
            {
              ...state.nominations[0],
              picked: true,
              bring: { person: null, owners_going: [ben, sam] },
            },
          ],
        }
        return Response.json(state)
      },
      [`PUT /api/meetups/${MEETUP_ID}/bring/1`]: () => {
        state = {
          ...state,
          nominations: [
            { ...state.nominations[0], bring: { person: sam, owners_going: [ben, sam] } },
          ],
        }
        return Response.json(state)
      },
    })

    expect(await screen.findByText('1 vote: Ben')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Vote' }))
    expect(await screen.findByText('2 votes: Ben, Sam')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Lock the pick' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByLabelText('Azul (2 votes)')).toBeChecked() // the most votes
    await userEvent.click(within(dialog).getByRole('button', { name: 'Lock' }))

    await waitFor(() => expect(locked).toEqual([['n1']]))
    expect(await screen.findByText('The pick')).toBeInTheDocument()
    expect(screen.getByText('Nobody’s bringing it yet')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'I’ll bring it' }))
    expect(await screen.findByText('Brought by Sam')).toBeInTheDocument()
    expect(screen.queryByText(/Too many/)).not.toBeInTheDocument()
  })

  it('flags games that can’t seat everyone going', async () => {
    const crowded: VoteState = {
      ...openVote,
      headcount: 5,
      nominations: [{ ...nomination, fits_now: false, fit: null }],
    }
    renderMeetup(meetupAt('2099-01-01T19:00:00Z'), {
      [`GET /api/meetups/${MEETUP_ID}/vote`]: () => Response.json(crowded),
    })

    expect(await screen.findByText('Too many: seats up to 4, 5 going')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Lock the pick' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Too many: seats up to 4, 5 going')).toBeInTheDocument()
  })
})

describe('Logging what was played', () => {
  beforeEach(() => signIn())

  it('starts from the pick and the yes answers, and saves who won', async () => {
    const notLogged: PlayLog = {
      logged: false,
      assumed: false,
      logged_at: null,
      can_log: true,
      attendees: [],
      plays: [],
      suggested_attendees: [ben, sam],
      suggested_games: [{ game: azul, coop: false }],
    }
    let sent: unknown
    renderMeetup(meetupAt('2020-01-01T19:00:00Z'), {
      [`GET /api/meetups/${MEETUP_ID}/vote`]: () =>
        Response.json({ ...openVote, locked: true, can_vote: false }),
      [`GET /api/meetups/${MEETUP_ID}/log`]: () => Response.json(notLogged),
      [`PUT /api/meetups/${MEETUP_ID}/log`]: async (request) => {
        sent = await request.json()
        return Response.json({
          ...notLogged,
          logged: true,
          attendees: [ben, sam],
          plays: [{ game: azul, coop: false, coop_won: null, players: [ben, sam], winners: [ben] }],
        })
      },
    })

    await userEvent.click(await screen.findByRole('button', { name: 'Log what we played' }))
    const dialog = await screen.findByRole('dialog')
    const winners = within(dialog).getAllByRole('checkbox', { name: 'Ben' })
    await userEvent.click(winners[winners.length - 1]) // the "Who won" row
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(sent).toEqual({
        attendees: [ben.id, sam.id],
        plays: [
          {
            game_id: 1,
            coop: false,
            coop_won: null,
            players: [ben.id, sam.id],
            winners: [ben.id],
          },
        ],
      }),
    )
    expect(await screen.findByText('Ben won')).toBeInTheDocument()
  })

  it('logs several games in the order played, including another round of one', async () => {
    const coup = { ...azul, id: 2, name: 'Coup' }
    const notLogged: PlayLog = {
      logged: false,
      assumed: false,
      logged_at: null,
      can_log: true,
      attendees: [],
      plays: [],
      suggested_attendees: [ben, sam],
      suggested_games: [
        { game: azul, coop: false },
        { game: coup, coop: false },
      ],
    }
    let sent: { plays: { game_id: number }[] } | undefined
    renderMeetup(meetupAt('2020-01-01T19:00:00Z'), {
      [`GET /api/meetups/${MEETUP_ID}/vote`]: () =>
        Response.json({ ...openVote, locked: true, can_vote: false }),
      [`GET /api/meetups/${MEETUP_ID}/log`]: () => Response.json(notLogged),
      [`PUT /api/meetups/${MEETUP_ID}/log`]: async (request) => {
        sent = await request.json()
        const row = (game: GameSummary) => ({
          game,
          coop: false,
          coop_won: null,
          players: [ben, sam],
          winners: [],
        })
        return Response.json({
          ...notLogged,
          logged: true,
          attendees: [ben, sam],
          plays: [row(coup), row(azul), row(coup)],
        })
      },
    })

    await userEvent.click(await screen.findByRole('button', { name: 'Log what we played' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getAllByLabelText('Add a game we played').length).toBeGreaterThan(0)

    await userEvent.click(within(dialog).getByRole('button', { name: 'Move Coup earlier' }))
    await userEvent.click(within(dialog).getAllByRole('button', { name: 'Played again' })[1]) // Azul
    expect(within(dialog).getByText('2. Azul · round 1')).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Remove Azul · round 2' }))
    await userEvent.click(within(dialog).getAllByRole('button', { name: 'Played again' })[0]) // Coup
    await userEvent.click(within(dialog).getByRole('button', { name: 'Move Coup · round 2 later' }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(sent?.plays.map((p) => p.game_id)).toEqual([2, 1, 2]))
    expect(await screen.findByText('3. Coup · round 2')).toBeInTheDocument()
    expect(screen.getByText('2. Azul')).toBeInTheDocument()
  })
})

describe('Voting on an online date', () => {
  beforeEach(() => signIn())

  const grand = {
    id: 990,
    slug: 'azul',
    name: 'Azul',
    premium: true,
    player_counts: [2, 4],
    status: 'public',
    game_url: 'https://boardgamearena.com/gamepanel?game=azul',
    lobby_url: 'https://boardgamearena.com/lobby?game=990',
  }
  const online = (): Meetup => ({
    ...meetupAt('2099-01-01T19:00:00Z'),
    location: null,
    is_online: true,
    online_url: 'https://boardgamearena.com/table?table=7',
  })
  const onlineVote: VoteState = {
    ...openVote,
    online: true,
    premium_host_going: false,
    nominations: [{ ...nomination, bga: grand }],
  }

  it('nominates any game on BGA and flags a Premium game nobody can start', async () => {
    const nominated: number[] = []
    renderMeetup(online(), {
      [`GET /api/meetups/${MEETUP_ID}/vote`]: () => Response.json(onlineVote),
      'GET /api/bga/games': () =>
        Response.json([
          { ...grand, id: 991, slug: 'carcassonne', name: 'Carcassonne', game: { ...azul, id: 2 } },
        ]),
      [`POST /api/meetups/${MEETUP_ID}/nominations`]: async (request) => {
        nominated.push(((await request.json()) as { game_id: number }).game_id)
        return Response.json(onlineVote)
      },
    })

    expect(await screen.findByText('Online · Board Game Arena')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Join the table' })).toHaveAttribute(
      'href',
      'https://boardgamearena.com/table?table=7',
    )
    expect(await screen.findByText('Premium: nobody going has it')).toBeInTheDocument()
    expect(screen.getByText('2, 4 players on BGA')).toBeInTheDocument()

    const picker = screen.getByRole('combobox', { name: 'Nominate any game on Board Game Arena' })
    await userEvent.type(picker, 'carc')
    await userEvent.click(await screen.findByRole('option', { name: 'Carcassonne (Premium)' }))
    await waitFor(() => expect(nominated).toEqual([2]))
  })

  it('shows where to play the pick, with nothing to bring', async () => {
    const lockedVote: VoteState = {
      ...onlineVote,
      locked: true,
      can_vote: false,
      premium_host_going: true,
      nominations: [{ ...nomination, bga: grand, picked: true }],
    }
    renderMeetup(online(), {
      [`GET /api/meetups/${MEETUP_ID}/vote`]: () => Response.json(lockedVote),
    })

    expect(await screen.findByText('The pick')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Start a table' })).toHaveAttribute(
      'href',
      'https://boardgamearena.com/lobby?game=990',
    )
    expect(screen.getByText('Premium')).toBeInTheDocument()
    expect(screen.queryByText('Nobody’s bringing it yet')).not.toBeInTheDocument()
  })
})
