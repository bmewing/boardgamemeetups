import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'

import { fetchMock, mockApi } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { UnsubscribePage } from './UnsubscribePage'

function renderPage(route: string) {
  renderWithProviders(
    <Routes>
      <Route path="/unsubscribe/:token" element={<UnsubscribePage />} />
    </Routes>,
    { route },
  )
}

describe('UnsubscribePage', () => {
  it('asks before turning a kind of email off, without signing in', async () => {
    let posted: string | null = null
    mockApi({
      'GET /api/email/unsubscribe/tok': () => Response.json({ email_opt_outs: [] }),
      'POST /api/email/unsubscribe/tok': (request) => {
        posted = new URL(request.url).search
        return Response.json({ email_opt_outs: ['rsvp_reminder'] })
      },
    })
    renderPage('/unsubscribe/tok?kind=rsvp_reminder')

    expect(
      await screen.findByText("Stop getting emails about dates you haven't answered?"),
    ).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1) // opening the link changes nothing
    await userEvent.click(screen.getByRole('button', { name: 'Stop these emails' }))

    expect(
      await screen.findByText(/You won't get any more emails about dates you haven't answered/),
    ).toBeInTheDocument()
    expect(posted).toBe('?kind=rsvp_reminder')
  })

  it('can stop every email', async () => {
    const all = [
      'friend_request',
      'group_invite',
      'rsvp_reminder',
      'pick_locked',
      'bringing',
      'date_changed',
    ]
    let posted: string | null = null
    mockApi({
      'GET /api/email/unsubscribe/tok': () => Response.json({ email_opt_outs: [] }),
      'POST /api/email/unsubscribe/tok': (request) => {
        posted = new URL(request.url).search
        return Response.json({ email_opt_outs: all })
      },
    })
    renderPage('/unsubscribe/tok?kind=bringing')

    await userEvent.click(await screen.findByRole('button', { name: 'Stop all emails' }))

    expect(
      await screen.findByText(/You won't get any more emails from Board Game Group/),
    ).toBeInTheDocument()
    expect(posted).toBe('')
  })

  it('says when a link no longer works', async () => {
    mockApi({
      'GET /api/email/unsubscribe/old': () => Response.json({ detail: 'gone' }, { status: 404 }),
    })
    renderPage('/unsubscribe/old?kind=bringing')

    expect(await screen.findByText(/This link doesn't work any more/)).toBeInTheDocument()
  })
})
