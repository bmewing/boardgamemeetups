import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { profile } from '../test/fixtures'
import { kindeAuth, mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { HomePage } from './HomePage'

const healthy = () => Response.json({ status: 'ok', database: 'ok' })

describe('HomePage', () => {
  it('shows signed-out visitors the landing page', () => {
    renderWithProviders(<HomePage />)

    expect(screen.getByRole('heading', { name: /Game night,\s*sorted\./ })).toBeInTheDocument()
    expect(screen.getByTestId('demo-round')).toHaveTextContent("Tonight's pick")
    expect(screen.queryByText('API status:')).not.toBeInTheDocument()
  })

  it('invites signed-out visitors to create an account', async () => {
    renderWithProviders(<HomePage />)

    await userEvent.click(screen.getByRole('button', { name: 'Get started' }))
    expect(kindeAuth.register).toHaveBeenCalledTimes(1)

    await userEvent.click(screen.getByRole('button', { name: 'Start a group' }))
    expect(kindeAuth.register).toHaveBeenCalledTimes(2)
  })

  it('lets signed-out visitors sign in', async () => {
    renderWithProviders(<HomePage />)

    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(kindeAuth.login).toHaveBeenCalled()
  })

  it('greets signed-in users by name', async () => {
    signIn()
    mockApi({ 'GET /api/health': healthy, 'GET /api/me': () => Response.json(profile) })

    renderWithProviders(<HomePage />)

    expect(await screen.findByRole('heading', { name: 'Welcome, Sam' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Get started' })).not.toBeInTheDocument()
    expect(screen.queryByTestId('demo-round')).not.toBeInTheDocument()
  })

  it('shows signed-in users the API and database status', async () => {
    signIn()
    mockApi({ 'GET /api/health': healthy, 'GET /api/me': () => Response.json(profile) })

    renderWithProviders(<HomePage />)

    expect(await screen.findByText('ok · database ok')).toBeInTheDocument()
  })

  it('shows unreachable when the API errors', async () => {
    signIn()
    mockApi({
      'GET /api/health': () => new Response('boom', { status: 500 }),
      'GET /api/me': () => Response.json(profile),
    })

    renderWithProviders(<HomePage />)

    expect(await screen.findByText('unreachable')).toBeInTheDocument()
  })
})
