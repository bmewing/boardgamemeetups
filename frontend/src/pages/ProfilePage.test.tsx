import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import { profile } from '../test/fixtures'
import { fetchMock, kindeAuth, mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { ProfilePage } from './ProfilePage'

describe('ProfilePage', () => {
  beforeEach(() => {
    signIn()
  })

  it('saves profile changes and sends the access token', async () => {
    let sent: unknown
    let authorization: string | null = null
    mockApi({
      'GET /api/me': () => Response.json(profile),
      'PATCH /api/me': async (request) => {
        sent = await request.json()
        authorization = request.headers.get('Authorization')
        return Response.json({ ...profile, display_name: 'Samantha' })
      },
    })
    renderWithProviders(<ProfilePage />)
    const name = await screen.findByLabelText('Display name')

    await userEvent.clear(name)
    await userEvent.type(name, 'Samantha')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Saved')).toBeInTheDocument()
    expect(sent).toMatchObject({ display_name: 'Samantha' })
    expect(authorization).toBe('Bearer test-token')
  })

  it('picks a piece and a color separately, each saving on its own', async () => {
    const sent: unknown[] = []
    let current = profile
    mockApi({
      'GET /api/me': () => Response.json(current),
      'PATCH /api/me': async (request) => {
        const body = (await request.json()) as Partial<typeof profile>
        sent.push(body)
        current = { ...current, ...body }
        return Response.json(current)
      },
    })
    renderWithProviders(<ProfilePage />)

    // No pick yet: a meeple.
    const meeple = await screen.findByRole('radio', { name: 'Meeple' })
    expect(meeple).toBeChecked()

    await userEvent.click(screen.getByRole('radio', { name: 'Top hat' }))
    await waitFor(() => expect(screen.getByRole('radio', { name: 'Top hat' })).toBeChecked())
    await userEvent.click(screen.getByRole('radio', { name: 'Plum' }))
    await waitFor(() => expect(screen.getByRole('radio', { name: 'Plum' })).toBeChecked())

    expect(sent).toEqual([{ piece: 'top_hat' }, { piece_color: 'plum' }])
    expect(screen.getByRole('img', { name: 'Plum top hat' })).toBeInTheDocument()
  })

  it('blocks saving a blank display name', async () => {
    mockApi({ 'GET /api/me': () => Response.json(profile) })
    renderWithProviders(<ProfilePage />)
    const name = await screen.findByLabelText('Display name')

    await userEvent.clear(name)
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Enter a display name')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.objectContaining({ method: 'PATCH' }),
      undefined,
    )
  })

  it('turns a kind of email off and back on', async () => {
    const sent: unknown[] = []
    let current = profile
    mockApi({
      'GET /api/me': () => Response.json(current),
      'PATCH /api/me': async (request) => {
        const body = (await request.json()) as { email_opt_outs: typeof profile.email_opt_outs }
        sent.push(body)
        current = { ...current, ...body }
        return Response.json(current)
      },
    })
    renderWithProviders(<ProfilePage />)
    const reminders = await screen.findByRole('switch', { name: /Reminders/ })
    expect(reminders).toBeChecked()

    await userEvent.click(reminders)
    await waitFor(() => expect(reminders).not.toBeChecked())
    await waitFor(() => expect(reminders).toBeEnabled())
    await userEvent.click(reminders)
    await waitFor(() => expect(reminders).toBeChecked())

    expect(sent).toEqual([{ email_opt_outs: ['rsvp_reminder'] }, { email_opt_outs: [] }])
  })

  it('shows the linked Discord account and unlinks it', async () => {
    mockApi({
      'GET /api/me': () => Response.json({ ...profile, discord_username: 'sam_d' }),
      'DELETE /api/me/discord': () => Response.json(profile),
    })
    renderWithProviders(<ProfilePage />)

    expect(await screen.findByText(/Linked to @sam_d/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Unlink Discord' }))

    expect(await screen.findByText(/Not linked/)).toBeInTheDocument()
  })

  it('deletes the account after confirmation and signs out', async () => {
    let deleted = false
    mockApi({
      'GET /api/me': () => Response.json(profile),
      'DELETE /api/me': () => {
        deleted = true
        return new Response(null, { status: 204 })
      },
    })
    renderWithProviders(<ProfilePage />)

    await userEvent.click(await screen.findByRole('button', { name: 'Delete my account' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Delete' }))

    await waitFor(() => expect(kindeAuth.logout).toHaveBeenCalled())
    expect(deleted).toBe(true)
  })
})
