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
const sam = { id: profile.id, display_name: 'Sam', avatar_url: null }
const ben = { id: '0190f0e2-0000-7000-8000-000000000002', display_name: 'Ben', avatar_url: null }

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
}

function meetupAt(startsAt: string, role: Meetup['my_role'] = 'owner'): Meetup {
  return {
    id: MEETUP_ID,
    local_date: startsAt.slice(0, 10),
    local_time: '19:00:00',
    starts_at: startsAt,
    duration_minutes: 180,
    location: null,
    status: 'scheduled',
    scheduled: false,
    edited: false,
    yes: 2,
    maybe: 0,
    no: 0,
    headcount: 2,
    my_response: 'yes',
    notes: null,
    group: { id: 'g1', name: 'Crew', time_zone: 'UTC', willing_to_split: false, plus_one_limit: 0 },
    my_role: role,
    rsvps: [
      { person: ben, response: 'yes', guests: 0, moods: [] },
      { person: sam, response: 'yes', guests: 0, moods: [] },
    ],
    no_answer: [],
    my_guests: 0,
    my_moods: [],
  }
}

const noGames: MeetupGames = {
  confirmed: 2,
  guests: 0,
  maybes: 0,
  willing_to_split: false,
  games: [],
  unknown_player_count: 0,
}

const nomination = {
  id: 'n1',
  game: azul,
  nominated_by: ben,
  votes: [ben],
  my_vote: false,
  picked: false,
  fits_now: true,
  bring: null,
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
})
