import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import type { FileColumns, FileImport, GameBrief } from '../api/fileImport'
import { mockApi, signIn } from '../test/mocks'
import { renderWithProviders } from '../test/render'
import { FileImportPage } from './FileImportPage'

const brief = (id: number, name: string, year: number): GameBrief => ({
  id,
  name,
  year_published: year,
  thumbnail_url: null,
  is_expansion: false,
})

const layout: FileColumns = {
  kind: 'table',
  has_header: true,
  headers: ['Name', 'Min Player', 'Status'],
  samples: [
    ['Azul', '2', 'Stack'],
    ['Clue', '3', ''],
  ],
  suggested: ['name', null, null],
  row_count: 2,
}

const matched: FileImport = {
  kind: 'table',
  filename: 'games.xlsx',
  rows: [
    {
      line: 2,
      name: 'Azul',
      year: null,
      bgg_id: null,
      values: { ownership: 'owned', notes: 'Stack' },
      problems: [],
      status: 'matched',
      confidence: 1,
      match: brief(1, 'Azul', 2017),
      candidates: [],
    },
    {
      line: 3,
      name: 'Clue',
      year: null,
      bgg_id: null,
      values: { ownership: 'owned' },
      problems: [],
      status: 'review',
      confidence: 1,
      match: brief(2, 'Clue', 1949),
      candidates: [
        { game: brief(2, 'Clue', 1949), score: 1 },
        { game: brief(3, 'Clue', 2012), score: 1 },
      ],
    },
  ],
}

function chooseFile(container: HTMLElement) {
  const input = container.querySelector('input[type=file]') as HTMLInputElement
  return userEvent.upload(input, new File(['xlsx bytes'], 'games.xlsx'))
}

describe('FileImportPage', () => {
  beforeEach(() => {
    signIn()
  })

  it('asks what each column holds and where the games go before matching', async () => {
    let matchUrl: URL | null = null
    mockApi({
      'POST /api/me/games/file-import/columns': () => Response.json(layout),
      'POST /api/me/games/file-import': (request) => {
        matchUrl = new URL(request.url)
        return Response.json(matched)
      },
    })
    const { container } = renderWithProviders(<FileImportPage />)

    await chooseFile(container)

    expect(await screen.findByText('2 rows found.', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('Azul · Clue')).toBeInTheDocument()
    const match = screen.getByRole('button', { name: 'Match games' })
    expect(match).toBeDisabled() // owned, wishlist or neither isn't chosen yet

    await userEvent.click(screen.getAllByLabelText('What Status holds')[0])
    await userEvent.click(await screen.findByRole('option', { name: /Notes/ }))
    await userEvent.click(screen.getByRole('radio', { name: 'Owned' }))
    await userEvent.click(match)

    expect(await screen.findByText(/1 row need a look/)).toBeInTheDocument()
    expect(matchUrl!.searchParams.getAll('columns')).toEqual(['name', '', 'notes'])
    expect(matchUrl!.searchParams.get('whole_file')).toBe('owned')
  })

  it('previews only rows with a confirmed game', async () => {
    const previewed: { games?: { game_id: number; values: unknown }[] } = {}
    mockApi({
      'POST /api/me/games/file-import/columns': () =>
        Response.json({ ...layout, suggested: ['name', null, 'ownership'] }),
      'POST /api/me/games/file-import': () => Response.json(matched),
      'POST /api/me/games/file-import/preview': async (request) => {
        Object.assign(previewed, await request.json())
        return Response.json({
          source: 'file',
          bgg_username: null,
          games: [],
          counts: {
            games_on_source: 1,
            new_games: 0,
            fills: 0,
            overwrites: 0,
            not_on_source: 0,
            removed_before: 0,
          },
        })
      },
    })
    const { container } = renderWithProviders(<FileImportPage />)
    await chooseFile(container)
    await userEvent.click(await screen.findByRole('button', { name: 'Match games' }))

    const clue = (await screen.findByText(/“Clue”/)).closest('div[class*="Card"]') as HTMLElement
    expect(within(clue).getByText('Which game is it?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Preview changes for 1 game' })).toBeInTheDocument()
    expect(
      screen.getByText('1 row without a game (or skipped) will be left out.'),
    ).toBeInTheDocument()

    await userEvent.click(within(clue).getByRole('button', { name: 'Clue (1949)' }))
    await userEvent.click(screen.getByRole('button', { name: 'Preview changes for 2 games' }))

    expect(await screen.findByText('Already up to date')).toBeInTheDocument()
    expect(previewed.games).toEqual([
      { game_id: 1, values: { ownership: 'owned', notes: 'Stack' } },
      { game_id: 2, values: { ownership: 'owned' } },
    ])
  })

  it('explains a file it cannot read', async () => {
    mockApi({
      'POST /api/me/games/file-import/columns': () =>
        Response.json({ detail: "This doesn't look like an Excel file" }, { status: 422 }),
    })
    const { container } = renderWithProviders(<FileImportPage />)

    await chooseFile(container)

    expect(await screen.findByText("This doesn't look like an Excel file")).toBeInTheDocument()
  })
})
