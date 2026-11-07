import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import type { AdminStats, AdminUser } from '../api/admin'
import { Layout } from '../components/Layout'
import { profile } from '../test/fixtures'
import { mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { AdminPage } from './AdminPage'

const admin = { ...profile, is_admin: true }

const stats: AdminStats = {
  users: {
    total: 42,
    new_7d: 3,
    new_30d: 9,
    active_7d: 17,
    active_30d: 30,
    banned: 1,
    admins: 1,
  },
  activity: {
    groups: 5,
    meetups_upcoming: 4,
    meetups_past: 20,
    plays_logged: 61,
    friendships: 12,
    games_owned: 800,
    catalog_games: 1200,
  },
  // Twelve Mondays, as the API sends them, with 0 to 11 sign-ups.
  signups_by_week: Array.from({ length: 12 }, (_, n) => ({
    week_start: new Date(Date.UTC(2026, 7, 17 + 7 * n)).toISOString().slice(0, 10),
    count: n,
  })),
}

const pat: AdminUser = {
  id: '0190f0e2-0000-7000-8000-000000000002',
  display_name: 'Pat',
  email: 'pat@example.com',
  avatar_url: null,
  piece: null,
  piece_color: null,
  is_admin: false,
  banned_at: null,
  ban_reason: null,
  created_at: '2026-11-01T00:00:00Z',
  last_seen_at: null,
  games_owned: 14,
  groups: 2,
}

const me: AdminUser = { ...pat, id: profile.id, display_name: 'Sam', is_admin: true }

describe('AdminPage', () => {
  beforeEach(() => signIn())

  it('turns away people who are not admins', async () => {
    mockApi({ 'GET /api/me': () => Response.json(profile) })

    renderWithProviders(<AdminPage />)

    expect(await screen.findByText('Only admins can see this page.')).toBeInTheDocument()
  })

  it('shows the stats and bans someone with a reason', async () => {
    let banned: unknown = null
    mockApi({
      'GET /api/me': () => Response.json(admin),
      'GET /api/admin/stats': () => Response.json(stats),
      'GET /api/admin/users': () => Response.json({ users: [me, pat], total: 2 }),
      [`PUT /api/admin/users/${pat.id}/ban`]: async (request) => {
        banned = await request.json()
        return Response.json({ ...pat, banned_at: '2026-11-05T00:00:00Z' })
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<AdminPage />)

    expect(await screen.findByText('42')).toBeInTheDocument()
    expect(screen.getByText('3 new this week')).toBeInTheDocument()
    expect(screen.getByText('Plays logged')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Sign-ups by week/ })).toBeInTheDocument()

    const row = (await screen.findByText('Pat')).closest('tr')!
    expect(within(row).getByText('Never')).toBeInTheDocument()
    // Your own row has no actions.
    expect(screen.queryByRole('button', { name: 'Actions for Sam' })).not.toBeInTheDocument()

    await user.click(within(row).getByRole('button', { name: 'Actions for Pat' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Ban…' }))
    await user.type(screen.getByLabelText('Reason'), 'Spam invites')
    await user.click(screen.getByRole('button', { name: 'Ban' }))

    await waitFor(() => expect(banned).toEqual({ reason: 'Spam invites' }))
  })

  it('deletes an account after confirming', async () => {
    let deleted = false
    mockApi({
      'GET /api/me': () => Response.json(admin),
      'GET /api/admin/stats': () => Response.json(stats),
      'GET /api/admin/users': () => Response.json({ users: deleted ? [] : [pat], total: 1 }),
      [`DELETE /api/admin/users/${pat.id}`]: () => {
        deleted = true
        return new Response(null, { status: 204 })
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<AdminPage />)

    await user.click(await screen.findByRole('button', { name: 'Actions for Pat' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Delete account…' }))
    await user.click(screen.getByRole('button', { name: 'Delete account' }))

    expect(await screen.findByText('Nobody matches.')).toBeInTheDocument()
    expect(deleted).toBe(true)
  })
})

describe('a suspended account', () => {
  beforeEach(() => signIn())

  it('sees only the suspension notice', async () => {
    mockApi({
      'GET /api/me': () =>
        Response.json({ detail: 'This account has been suspended.' }, { status: 403 }),
    })

    renderWithProviders(<Layout />)

    expect(await screen.findByText('Account suspended')).toBeInTheDocument()
    expect(screen.getByText(/This account has been suspended\./)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Search' })).not.toBeInTheDocument()
  })
})
