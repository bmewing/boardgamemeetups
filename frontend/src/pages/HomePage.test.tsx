import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../test/render'
import { HomePage } from './HomePage'

// openapi-fetch captures fetch when the client module loads, so stub it before imports.
const { fetchMock } = vi.hoisted(() => {
  const fetchMock = vi.fn<typeof fetch>()
  globalThis.fetch = fetchMock
  return { fetchMock }
})

describe('HomePage', () => {
  beforeEach(() => {
    fetchMock.mockReset()
  })

  it('shows the API and database status', async () => {
    fetchMock.mockResolvedValue(Response.json({ status: 'ok', database: 'ok' }))

    renderWithProviders(<HomePage />)

    expect(await screen.findByText('ok · database ok')).toBeInTheDocument()
  })

  it('shows unreachable when the API errors', async () => {
    fetchMock.mockResolvedValue(new Response('boom', { status: 500 }))

    renderWithProviders(<HomePage />)

    expect(await screen.findByText('unreachable')).toBeInTheDocument()
  })
})
