import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'

import type { Group, Meetup, MeetupBrief } from '../api/groups'
import type { Character, Party, RpgSystemSummary } from '../api/rpg'
import { profile } from '../test/fixtures'
import { mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { CharactersPage } from './CharactersPage'
import { GroupPage } from './GroupPage'
import { GroupsPage } from './GroupsPage'
import { MeetupPage } from './MeetupPage'

const GROUP_ID = '0190f0e2-0000-7000-8000-0000000000c1'
const MEETUP_ID = '0190f0e2-0000-7000-8000-0000000000d1'
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
const blades: RpgSystemSummary = {
  id: 26952,
  name: 'Blades in the Dark',
  thumbnail_url: null,
  is_custom: false,
}

const brief: MeetupBrief = {
  id: MEETUP_ID,
  local_date: '2026-11-05',
  local_time: '19:00:00',
  starts_at: '2026-11-06T01:00:00Z',
  duration_minutes: 180,
  location: null,
  status: 'scheduled',
  scheduled: false,
  edited: false,
  yes: 2,
  maybe: 0,
  no: 0,
  headcount: 2,
  going: [],
  my_response: 'yes',
}

const group: Group = {
  id: GROUP_ID,
  name: 'Duskwall Crew',
  description: null,
  kind: 'rpg',
  rpg_system: blades,
  time_zone: 'UTC',
  willing_to_split: false,
  schedule: null,
  start_time: '19:00:00',
  duration_minutes: 180,
  location: null,
  plus_one_limit: 0,
  my_role: 'owner',
  members: [
    { person: sam, role: 'owner', is_gm: true, joined_at: '2026-11-01T00:00:00Z' },
    { person: ben, role: 'member', is_gm: false, joined_at: '2026-11-02T00:00:00Z' },
  ],
  invites: [],
  upcoming: [],
  recent: [],
}

const character = (over: Partial<Character> = {}): Character => ({
  id: '0190f0e2-0000-7000-8000-0000000000e1',
  owner: ben,
  system: blades,
  name: 'Vex',
  class_role: 'Cutter',
  level: 2,
  ancestry: 'Skovlander',
  pronouns: 'she/her',
  status: 'active',
  notes: null,
  portrait_url: null,
  sheet_url: null,
  group: { id: GROUP_ID, name: 'Duskwall Crew' },
  created_at: '2026-11-03T00:00:00Z',
  updated_at: '2026-11-03T00:00:00Z',
  ...over,
})

describe('RPG groups', () => {
  beforeEach(() => signIn())

  it('makes an RPG group playing a system, without the board-game options', async () => {
    let sent: unknown
    mockApi({
      'GET /api/me': () => Response.json(profile),
      'GET /api/groups': () => Response.json({ groups: [], invites: [] }),
      'GET /api/rpg-systems/search': () => Response.json([blades]),
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
    expect(await screen.findByText(/Happy to split/)).toBeInTheDocument()
    await userEvent.click(screen.getByText('Tabletop RPG'))
    expect(screen.queryByText(/Happy to split/)).not.toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/Name/), 'Duskwall Crew')
    await userEvent.type(screen.getAllByLabelText('System')[0], 'blades')
    await userEvent.click(await screen.findByRole('option', { name: 'Blades in the Dark' }))
    await userEvent.click(screen.getByRole('button', { name: 'Make the group' }))

    expect(await screen.findByText('Group page')).toBeInTheDocument()
    expect(sent).toMatchObject({
      name: 'Duskwall Crew',
      kind: 'rpg',
      rpg_system_id: blades.id,
      willing_to_split: false,
    })
  })

  it('shows the party in place of the games, with GMs and what members know', async () => {
    const party: Party = {
      system: blades,
      characters: [character()],
      members: [
        {
          person: sam,
          is_gm: true,
          answers: { knows: true, can_gm: true, want_to_play: false },
        },
        { person: ben, is_gm: false, answers: null },
      ],
    }
    mockApi({
      'GET /api/me': () => Response.json(profile),
      [`GET /api/groups/${GROUP_ID}`]: () => Response.json(group),
      [`GET /api/groups/${GROUP_ID}/party`]: () => Response.json(party),
      'GET /api/me/characters': () => Response.json([]),
    })
    renderWithProviders(
      <Routes>
        <Route path="/groups/:groupId" element={<GroupPage />} />
      </Routes>,
      { route: `/groups/${GROUP_ID}` },
    )

    expect(await screen.findByRole('tab', { name: 'Party' })).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Games' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('tab', { name: 'Party' }))

    expect(await screen.findByText('Vex')).toBeInTheDocument()
    expect(screen.getByText('Level 2 Skovlander Cutter')).toBeInTheDocument()
    expect(screen.getByText('played by Ben')).toBeInTheDocument()
    expect(screen.getByText('Who knows Blades in the Dark')).toBeInTheDocument()
    expect(screen.getByText('Can GM it')).toBeInTheDocument()
    expect(screen.getByText("Hasn't said")).toBeInTheDocument()

    await userEvent.click(screen.getByRole('tab', { name: /Members/ }))
    expect(await screen.findByText('Owner · GM')).toBeInTheDocument()
  })

  it('shows a recap in place of game picks once the session has started', async () => {
    let saved: unknown
    const meetup: Meetup = {
      ...brief,
      notes: null,
      recap: null,
      recap_updated_at: null,
      previous_recap: null,
      group: {
        id: GROUP_ID,
        name: 'Duskwall Crew',
        kind: 'rpg',
        time_zone: 'UTC',
        willing_to_split: false,
        plus_one_limit: 0,
      },
      my_role: 'member',
      rsvps: [
        { person: sam, response: 'yes', guests: 0, moods: [] },
        { person: ben, response: 'yes', guests: 0, moods: [] },
      ],
      no_answer: [],
      my_guests: 0,
      my_moods: [],
    }
    mockApi({
      'GET /api/me': () => Response.json(profile),
      [`GET /api/meetups/${MEETUP_ID}`]: () => Response.json(meetup),
      'GET /api/moods': () =>
        Response.json([{ id: 'chill', name: 'Chill', description: '', taggable: true }]),
      [`PUT /api/meetups/${MEETUP_ID}/recap`]: async (request) => {
        saved = await request.json()
        return Response.json({ ...meetup, recap: 'We stole the bell.' })
      },
    })
    renderWithProviders(
      <Routes>
        <Route path="/meetups/:meetupId" element={<MeetupPage />} />
      </Routes>,
      { route: `/meetups/${MEETUP_ID}` },
    )

    expect(await screen.findByText('Session recap')).toBeInTheDocument()
    expect(screen.queryByText(/in the mood for/)).not.toBeInTheDocument()
    expect(screen.queryByText('Recommended games')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Write the recap' }))
    await userEvent.type(screen.getByLabelText('Session recap'), 'We stole the bell.')
    await userEvent.click(screen.getByRole('button', { name: 'Save recap' }))

    await waitFor(() => expect(saved).toEqual({ recap: 'We stole the bell.' }))
    expect(await screen.findByText('We stole the bell.')).toBeInTheDocument()
  })
})

describe('Characters', () => {
  beforeEach(() => signIn())

  it('makes a character in a system, checking its links', async () => {
    let sent: unknown
    const made = character({ owner: sam, group: null })
    mockApi({
      'GET /api/me': () => Response.json(profile),
      'GET /api/me/characters': () => Response.json([]),
      'GET /api/rpg-systems/search': () => Response.json([blades]),
      'POST /api/me/characters': async (request) => {
        sent = await request.json()
        return Response.json(made, { status: 201 })
      },
    })
    renderWithProviders(
      <Routes>
        <Route path="/" element={<CharactersPage />} />
        <Route path="/characters/:characterId" element={<p>Character page</p>} />
      </Routes>,
    )

    expect(await screen.findByText('No characters yet')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'New character' }))
    await userEvent.type(await screen.findByLabelText(/^Name/), 'Vex')
    await userEvent.type(screen.getAllByLabelText(/^System/)[0], 'blades')
    await userEvent.click(await screen.findByRole('option', { name: 'Blades in the Dark' }))
    await userEvent.type(screen.getByLabelText('Class or role'), 'Cutter')
    await userEvent.type(screen.getByLabelText('Level'), '2')
    await userEvent.type(screen.getByLabelText('Character sheet link'), 'not a link')
    await userEvent.click(screen.getByRole('button', { name: 'Make character' }))

    expect(await screen.findByText(/need to start with http/)).toBeInTheDocument()
    expect(sent).toBeUndefined()

    await userEvent.clear(screen.getByLabelText('Character sheet link'))
    await userEvent.type(screen.getByLabelText('Character sheet link'), 'https://example.com/vex')
    await userEvent.click(screen.getByRole('button', { name: 'Make character' }))

    expect(await screen.findByText('Character page')).toBeInTheDocument()
    expect(sent).toEqual({
      name: 'Vex',
      system_id: blades.id,
      class_role: 'Cutter',
      level: 2,
      ancestry: null,
      pronouns: null,
      status: 'active',
      notes: null,
      portrait_url: null,
      sheet_url: 'https://example.com/vex',
      group_id: null,
    })
  })
})
