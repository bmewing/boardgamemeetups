import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import type { Friends, Person } from '../api/friends'
import { mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { FriendsPage } from './FriendsPage'

const ben: Person = {
  id: '0190f0e2-0000-7000-8000-000000000002',
  display_name: 'Ben',
  avatar_url: null,
  piece: null,
  piece_color: null,
}
const cat: Person = {
  id: '0190f0e2-0000-7000-8000-000000000003',
  display_name: 'Cat',
  avatar_url: null,
  piece: null,
  piece_color: null,
}
const since = '2026-11-03T12:00:00Z'
const none: Friends = { friends: [], incoming: [], outgoing: [] }

function serve(friends: Friends, extra: Parameters<typeof mockApi>[0] = {}) {
  mockApi({
    'GET /api/friends': () => Response.json(friends),
    'GET /api/blocks': () => Response.json([]),
    'GET /api/invite-links': () => Response.json([]),
    ...extra,
  })
}

describe('FriendsPage', () => {
  beforeEach(() => {
    signIn()
  })

  it('sends a request by email', async () => {
    let sent: unknown
    serve(none, {
      'POST /api/friends/requests': async (request) => {
        sent = await request.json()
        return Response.json({ person: ben, relation: 'outgoing' })
      },
    })
    renderWithProviders(<FriendsPage />)

    await userEvent.type(await screen.findByLabelText(/Find someone/), 'ben@example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Send request' }))

    expect(await screen.findByText('Request sent to Ben.')).toBeInTheDocument()
    expect(sent).toEqual({ email: 'ben@example.com' })
  })

  it('suggests people as you type and sends to the one picked', async () => {
    let sent: unknown
    let searched = ''
    serve(none, {
      'GET /api/people/search': (request) => {
        searched = new URL(request.url).searchParams.get('q') ?? ''
        return Response.json([{ person: ben, relation: 'none' }])
      },
      'POST /api/friends/requests': async (request) => {
        sent = await request.json()
        return Response.json({ person: ben, relation: 'outgoing' })
      },
    })
    renderWithProviders(<FriendsPage />)

    await userEvent.type(await screen.findByLabelText(/Find someone/), 'Be')
    await userEvent.click(await screen.findByRole('option', { name: /Ben/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Send request' }))

    expect(await screen.findByText('Request sent to Ben.')).toBeInTheDocument()
    expect(searched).toBe('Be')
    expect(sent).toEqual({ user_id: ben.id })
  })

  it('asks for a pick or a full email', async () => {
    serve(none, { 'GET /api/people/search': () => Response.json([]) })
    renderWithProviders(<FriendsPage />)

    await userEvent.type(await screen.findByLabelText(/Find someone/), 'Zed')
    await userEvent.click(screen.getByRole('button', { name: 'Send request' }))

    expect(
      await screen.findByText(
        'Pick someone from the suggestions, or type their full email address.',
      ),
    ).toBeInTheDocument()
  })

  it('points to invite links when nobody has that email', async () => {
    serve(none, {
      'POST /api/friends/requests': () =>
        Response.json({ detail: 'No one here uses that email yet.' }, { status: 404 }),
    })
    renderWithProviders(<FriendsPage />)

    await userEvent.type(await screen.findByLabelText(/Find someone/), 'new@example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Send request' }))

    expect(await screen.findByText('No one here uses that email yet')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Make an invite link' })).toBeInTheDocument()
  })

  it('accepts an incoming request', async () => {
    let friends: Friends = { ...none, incoming: [{ person: ben, since }] }
    serve(friends, {
      'GET /api/friends': () => Response.json(friends),
      [`POST /api/friends/${ben.id}/accept`]: () => {
        friends = { ...none, friends: [{ person: ben, since }] }
        return Response.json({ person: ben, relation: 'friends' })
      },
    })
    renderWithProviders(<FriendsPage />)

    await userEvent.click(await screen.findByRole('button', { name: 'Accept' }))

    await waitFor(() =>
      expect(screen.queryByText('Asking to be your friend')).not.toBeInTheDocument(),
    )
    expect(screen.getByRole('link', { name: 'Ben' })).toHaveAttribute('href', `/people/${ben.id}`)
  })

  it('makes and lists invite links', async () => {
    const link = {
      id: 'l1',
      token: 'abc123',
      created_at: since,
      expires_at: '2026-12-03T12:00:00Z',
      use_count: 2,
    }
    let links: (typeof link)[] = []
    serve(
      { ...none, outgoing: [{ person: cat, since }] },
      {
        'GET /api/invite-links': () => Response.json(links),
        'POST /api/invite-links': () => {
          links = [link]
          return Response.json(link, { status: 201 })
        },
      },
    )
    renderWithProviders(<FriendsPage />)

    expect(await screen.findByText('Waiting for an answer')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Make an invite link' }))

    expect(await screen.findByDisplayValue(`${window.location.origin}/invite/abc123`)).toBeVisible()
    expect(screen.getByText(/2 friends joined/)).toBeInTheDocument()
  })
})
