import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { afterEach, describe, expect, it } from 'vitest'

import { profile } from '../test/fixtures'
import { kindeAuth, mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { InvitePage } from './InvitePage'

const ann = {
  id: '0190f0e2-0000-7000-8000-000000000009',
  display_name: 'Ann',
  avatar_url: null,
  piece: null,
  piece_color: null,
}

function renderInvite(token = 'tok') {
  renderWithProviders(
    <Routes>
      <Route path="/invite/:token" element={<InvitePage />} />
      <Route path="/people/:userId" element={<p>Ann's page</p>} />
    </Routes>,
    { route: `/invite/${token}` },
  )
}

describe('InvitePage', () => {
  afterEach(() => sessionStorage.clear())

  it('says who invited you and remembers the link through sign-up', async () => {
    mockApi({ 'GET /api/invites/tok': () => Response.json({ inviter: ann }) })
    renderInvite()

    expect(await screen.findByText('Ann invited you to be friends')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Create an account' }))

    expect(kindeAuth.register).toHaveBeenCalled()
    expect(sessionStorage.getItem('pendingInvite')).toBe('tok')
  })

  it('becomes friends once signed in', async () => {
    signIn()
    sessionStorage.setItem('pendingInvite', 'tok')
    let accepted = false
    mockApi({
      'GET /api/me': () => Response.json(profile),
      'GET /api/invites/tok': () => Response.json({ inviter: ann }),
      'POST /api/invites/tok/accept': () => {
        accepted = true
        return Response.json({ person: ann, relation: 'friends' })
      },
    })
    renderInvite()

    await userEvent.click(await screen.findByRole('button', { name: 'Become friends with Ann' }))

    expect(await screen.findByText("Ann's page")).toBeInTheDocument()
    expect(accepted).toBe(true)
    expect(sessionStorage.getItem('pendingInvite')).toBeNull()
  })

  it('explains a dead link', async () => {
    mockApi({
      'GET /api/invites/old': () => Response.json({ detail: 'gone' }, { status: 404 }),
    })
    renderInvite('old')

    expect(
      await screen.findByText('This invite link has expired or been turned off.'),
    ).toBeInTheDocument()
  })
})
