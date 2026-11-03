import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import type { ChangeIn, ImportPreview } from '../api/collection'
import { profile } from '../test/fixtures'
import { mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { BggPullPage } from './BggPullPage'

const brief = (id: number, name: string) => ({
  id,
  name,
  year_published: 2020,
  thumbnail_url: null,
  is_expansion: false,
})

const preview: ImportPreview = {
  source: 'bgg',
  bgg_username: 'sam_bgg',
  counts: { games_on_source: 3, new_games: 1, fills: 2, overwrites: 1, not_on_source: 1 },
  games: [
    {
      game: brief(1, 'Azul'),
      is_new: true,
      on_source: true,
      changes: [
        { field: 'ownership', current: null, incoming: 'owned', kind: 'fill' },
        { field: 'plays', current: 0, incoming: 4, kind: 'fill' },
      ],
    },
    {
      game: brief(2, 'Brass'),
      is_new: false,
      on_source: true,
      changes: [{ field: 'rating', current: 6, incoming: 9, kind: 'overwrite' }],
    },
    {
      game: brief(3, 'Catan'),
      is_new: false,
      on_source: false,
      changes: [{ field: 'ownership', current: 'owned', incoming: null, kind: 'not_on_source' }],
    },
  ],
}

function mockPull(applied: { changes?: ChangeIn[] } = {}) {
  mockApi({
    'GET /api/me': () => Response.json({ ...profile, bgg_username: 'sam_bgg' }),
    'POST /api/me/games/bgg-pull': () => Response.json(preview),
    'POST /api/me/games/import': async (request) => {
      const body = (await request.json()) as { changes: ChangeIn[] }
      applied.changes = body.changes
      return Response.json({ applied: body.changes.length, skipped: [] })
    },
    'GET /api/me/games': () => Response.json([]),
  })
}

describe('BggPullPage', () => {
  beforeEach(() => {
    signIn()
  })

  it('asks for a BGG username first', async () => {
    mockApi({ 'GET /api/me': () => Response.json(profile) })
    renderWithProviders(<BggPullPage />)

    expect(await screen.findByText('Add your BGG username first')).toBeInTheDocument()
  })

  it('previews every change and says how much would be overwritten', async () => {
    mockPull()
    renderWithProviders(<BggPullPage />)

    await userEvent.click(await screen.findByRole('button', { name: 'Fetch from BGG' }))

    expect(
      await screen.findByText('It would overwrite 1 answer you gave here.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/Pulling would add 1 new game and fill 2 blanks/)).toBeInTheDocument()
    expect(screen.getByText('New games (1)')).toBeInTheDocument()
    expect(screen.getByText('Ownership: Owned · Plays: 4')).toBeInTheDocument()
    const brass = screen.getByText('Brass').closest('div[class*="Card"]') as HTMLElement
    expect(within(brass).getByText('Overwrites yours')).toBeInTheDocument()
    expect(within(brass).getByRole('checkbox')).toBeChecked()
    // Clearing a game BGG no longer lists is opt-in.
    const catan = screen.getByText('Catan').closest('div[class*="Card"]') as HTMLElement
    expect(within(catan).getByRole('checkbox')).not.toBeChecked()
    expect(
      screen.getByRole('button', { name: 'Apply 3 changes (1 overwrite yours)' }),
    ).toBeInTheDocument()
  })

  it('applies only the changes left ticked', async () => {
    const applied: { changes?: ChangeIn[] } = {}
    mockPull(applied)
    renderWithProviders(<BggPullPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Fetch from BGG' }))

    const brass = (await screen.findByText('Brass')).closest('div[class*="Card"]') as HTMLElement
    await userEvent.click(within(brass).getByRole('checkbox'))
    await userEvent.click(screen.getByRole('button', { name: 'Apply 2 changes' }))

    expect(await screen.findByText('Applied 2 changes.')).toBeInTheDocument()
    expect(applied.changes).toEqual([
      { game_id: 1, field: 'ownership', expected: null, value: 'owned' },
      { game_id: 1, field: 'plays', expected: 0, value: 4 },
    ])
  })

  it('explains BGG problems and offers a retry', async () => {
    mockApi({
      'GET /api/me': () => Response.json({ ...profile, bgg_username: 'sam_bgg' }),
      'POST /api/me/games/bgg-pull': () =>
        Response.json(
          { detail: 'BGG is still preparing your collection; try again in a minute' },
          { status: 503 },
        ),
    })
    renderWithProviders(<BggPullPage />)

    await userEvent.click(await screen.findByRole('button', { name: 'Fetch from BGG' }))

    expect(await screen.findByText(/still preparing your collection/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})
