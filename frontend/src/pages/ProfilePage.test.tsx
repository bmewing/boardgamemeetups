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
