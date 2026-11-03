import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { profile } from '../test/fixtures'
import { kindeAuth, mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { HomePage } from './HomePage'

const healthy = () => Response.json({ status: 'ok', database: 'ok' })

describe('HomePage', () => {
  it('shows the API and database status', async () => {
    mockApi({ 'GET /api/health': healthy })

    renderWithProviders(<HomePage />)

    expect(await screen.findByText('ok · database ok')).toBeInTheDocument()
  })

  it('shows unreachable when the API errors', async () => {
    mockApi({ 'GET /api/health': () => new Response('boom', { status: 500 }) })

    renderWithProviders(<HomePage />)

    expect(await screen.findByText('unreachable')).toBeInTheDocument()
  })

  it('invites signed-out visitors to create an account', async () => {
    mockApi({ 'GET /api/health': healthy })
    renderWithProviders(<HomePage />)

    await userEvent.click(screen.getByRole('button', { name: 'Get started' }))

    expect(kindeAuth.register).toHaveBeenCalled()
  })

  it('greets signed-in users by name', async () => {
    signIn()
    mockApi({ 'GET /api/health': healthy, 'GET /api/me': () => Response.json(profile) })

    renderWithProviders(<HomePage />)

    expect(await screen.findByRole('heading', { name: 'Welcome, Sam' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Get started' })).not.toBeInTheDocument()
  })
})
