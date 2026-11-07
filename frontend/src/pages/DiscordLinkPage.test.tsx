import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { afterEach, describe, expect, it } from 'vitest'

import { profile } from '../test/fixtures'
import { kindeAuth, mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { DiscordLinkPage } from './DiscordLinkPage'

function renderPage(token = 'tok') {
  renderWithProviders(
    <Routes>
      <Route path="/discord/link/:token" element={<DiscordLinkPage />} />
    </Routes>,
    { route: `/discord/link/${token}` },
  )
}

describe('DiscordLinkPage', () => {
  afterEach(() => sessionStorage.clear())

  it('names the Discord account and remembers the link through sign-in', async () => {
    mockApi({ 'GET /api/discord/link/tok': () => Response.json({ discord_username: 'ann_d' }) })
    renderPage()

    expect(await screen.findByText('@ann_d')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Sign in to link' }))

    expect(kindeAuth.login).toHaveBeenCalled()
    expect(sessionStorage.getItem('pendingDiscordLink')).toBe('tok')
  })

  it('links once signed in and asked to', async () => {
    signIn()
    let sent: unknown
    mockApi({
      'GET /api/me': () => Response.json(profile),
      'GET /api/discord/link/tok': () => Response.json({ discord_username: 'ann_d' }),
      'PUT /api/me/discord': async (request) => {
        sent = await request.json()
        return Response.json({ ...profile, discord_username: 'ann_d' })
      },
    })
    renderPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Link my account' }))

    expect(await screen.findByText("Linked! Discord's @ann_d is you.")).toBeInTheDocument()
    expect(sent).toEqual({ token: 'tok' })
  })

  it('says when the link has expired', async () => {
    mockApi({
      'GET /api/discord/link/old': () =>
        Response.json({ detail: 'This link has expired.' }, { status: 404 }),
    })
    renderPage('old')

    expect(await screen.findByText('This link has expired.')).toBeInTheDocument()
  })
})
