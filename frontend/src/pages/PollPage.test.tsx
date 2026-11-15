import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Poll } from '../api/polls'
import { datesBetween } from '../components/polls/pollFormat'
import { dayLabel, stretchLabel, timeLabel } from '../components/polls/pollFormat'
import { mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { PollPage } from './PollPage'

const POLL_ID = '0190f0e2-0000-7000-8000-0000000000c1'
const GROUP_ID = '0190f0e2-0000-7000-8000-0000000000a1'
const person = (name: string, id: string) => ({
  id,
  display_name: name,
  avatar_url: null,
  piece: null,
  piece_color: null,
})
const ann = person('Ann', '0190f0e2-0000-7000-8000-000000000001')
const ben = person('Ben', '0190f0e2-0000-7000-8000-000000000002')

const poll: Poll = {
  id: POLL_ID,
  group_id: GROUP_ID,
  group_name: 'Thursday Crew',
  title: 'Trivia night',
  status: 'open',
  time_zone: 'America/New_York',
  slot_minutes: 30,
  duration_minutes: 60,
  days: [{ date: '2026-11-19', slots: ['2026-11-19T19:00', '2026-11-19T19:30'] }],
  can_manage: false,
  my_slots: null,
  respondents: [{ person: ben, slots: ['2026-11-19T19:00'] }],
  waiting: [ann],
  best: [],
  meetup_id: null,
  created_by: ben,
}

function renderPoll() {
  return renderWithProviders(
    <Routes>
      <Route path="/polls/:pollId" element={<PollPage />} />
    </Routes>,
    { route: `/polls/${POLL_ID}` },
  )
}

describe('formatting', () => {
  it('labels slots by their own wall-clock parts', () => {
    expect(dayLabel('2026-11-19')).toBe('Thu, Nov 19')
    expect(timeLabel('2026-11-19T19:00')).toMatch(/^7:00\s?PM$/i)
    expect(timeLabel('24:00')).toMatch(/^12:00\s?AM$/i)
    expect(stretchLabel('2026-11-19T19:00', '21:00')).toMatch(
      /^Thu, Nov 19 · 7:00\s?PM–9:00\s?PM$/i,
    )
  })

  it('offers only the chosen weekdays between two dates', () => {
    // Nov 19 2026 is a Thursday; skip weekends.
    expect(datesBetween('2026-11-19', '2026-11-24', [1, 2, 3, 4, 5])).toEqual([
      '2026-11-19',
      '2026-11-20',
      '2026-11-23',
      '2026-11-24',
    ])
  })
})

describe('PollPage', () => {
  beforeEach(() => signIn())

  it('opens on My times for someone who has not answered, showing others on slots', async () => {
    mockApi({ [`GET /api/polls/${POLL_ID}`]: () => Response.json(poll) })
    renderPoll()

    const slot = await screen.findByRole('button', { name: /7:00\s?PM.*1 free/i })
    expect(slot).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: /None of these work/ })).toBeInTheDocument()
    expect(screen.getByText(/waiting on Ann/)).toBeInTheDocument()
  })

  it('saves two quick taps as one answer', async () => {
    const puts: string[][] = []
    mockApi({
      [`GET /api/polls/${POLL_ID}`]: () => Response.json(poll),
      [`PUT /api/polls/${POLL_ID}/answer`]: async (request) => {
        const { slots } = (await request.json()) as { slots: string[] }
        puts.push(slots)
        return Response.json({ ...poll, my_slots: slots })
      },
    })
    const user = userEvent.setup()
    renderPoll()

    const first = await screen.findByRole('button', { name: /7:00\s?PM/i })
    await user.click(first)
    await user.click(screen.getByRole('button', { name: /7:30\s?PM/i }))

    expect(screen.getByRole('button', { name: /7:00\s?PM/i })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('button', { name: /7:30\s?PM/i })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await waitFor(() => expect(puts).toHaveLength(1), { timeout: 3000 })
    expect(puts[0]).toEqual(['2026-11-19T19:00', '2026-11-19T19:30'])
    expect(await screen.findByText('Saved')).toBeInTheDocument()
  })

  it('opens on Everyone once you have answered, without Schedule it for non-organizers', async () => {
    mockApi({
      [`GET /api/polls/${POLL_ID}`]: () =>
        Response.json({
          ...poll,
          my_slots: ['2026-11-19T19:00'],
          respondents: [
            { person: ann, slots: ['2026-11-19T19:00'] },
            { person: ben, slots: ['2026-11-19T19:00'] },
          ],
          waiting: [],
          best: [
            {
              start: '2026-11-19T19:00',
              end: '20:00',
              starts_at: '2026-11-19T19:00:00-05:00',
              available: [ann, ben],
              missing: [],
            },
          ],
        } satisfies Poll),
    })
    renderPoll()

    expect(await screen.findByText('Best times')).toBeInTheDocument()
    expect(screen.getByText(/Everyone who answered \(2\)/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Schedule it' })).not.toBeInTheDocument()
  })

  it('lets an organizer schedule a best time', async () => {
    const scheduled: string[] = []
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const withBest: Poll = {
      ...poll,
      can_manage: true,
      my_slots: [],
      best: [
        {
          start: '2026-11-19T19:00',
          end: '20:00',
          starts_at: '2026-11-19T19:00:00-05:00',
          available: [ben],
          missing: [],
        },
      ],
    }
    mockApi({
      [`GET /api/polls/${POLL_ID}`]: () => Response.json(withBest),
      [`POST /api/polls/${POLL_ID}/schedule`]: async (request) => {
        scheduled.push(((await request.json()) as { start: string }).start)
        return Response.json({ ...withBest, status: 'closed', meetup_id: 'm1' })
      },
    })
    const user = userEvent.setup()
    renderPoll()

    await user.click(await screen.findByRole('button', { name: 'Schedule it' }))

    await waitFor(() => expect(scheduled).toEqual(['2026-11-19T19:00']))
  })
})
