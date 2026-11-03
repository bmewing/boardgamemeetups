import { useMutation } from '@tanstack/react-query'

import { api } from './client'
import { detailOf, type UserGameUpdate } from './collection'
import type { components } from './schema'

export type FileColumns = components['schemas']['FileColumnsRead']
export type FileImport = components['schemas']['FileImportRead']
export type FileRow = components['schemas']['FileRowRead']
export type ImportColumn = components['schemas']['ImportColumn']
export type WholeFile = components['schemas']['WholeFile']
export type GameBrief = components['schemas']['GameBrief']

// The file goes up as the request body, as raw bytes: the API reads it, stores nothing.
const asFile = {
  bodySerializer: (file: unknown) => file as BodyInit,
  headers: { 'Content-Type': 'application/octet-stream' },
}

/** The file's columns, with sample values and a guess at what each one holds. */
export function useFileColumns() {
  return useMutation({
    mutationFn: async (file: File) => {
      const { data, error } = await api.POST('/api/me/games/file-import/columns', {
        params: { query: { filename: file.name } },
        body: file as unknown as string,
        ...asFile,
      })
      if (error) throw new Error(detailOf(error, 'Could not read this file'))
      return data
    },
  })
}

export interface MatchRequest {
  file: File
  /** One per file column: what it holds, or null to ignore it. Unused for a BGG export. */
  columns: (ImportColumn | null)[]
  wholeFile: WholeFile | null
}

/** Read every row with the chosen columns and match each to a game. */
export function useMatchFile() {
  return useMutation({
    mutationFn: async ({ file, columns, wholeFile }: MatchRequest) => {
      const { data, error } = await api.POST('/api/me/games/file-import', {
        params: {
          query: {
            filename: file.name,
            columns: columns.map((c) => c ?? ''),
            ...(wholeFile ? { whole_file: wholeFile } : {}),
          },
        },
        body: file as unknown as string,
        ...asFile,
      })
      if (error) throw new Error(detailOf(error, 'Could not read this file'))
      return data
    },
  })
}

export interface FileGame {
  gameId: number
  values: UserGameUpdate
}

/** What importing these games would change. Writes nothing. */
export function useFilePreview() {
  return useMutation({
    mutationFn: async ({
      games,
      wholeBggCollection,
    }: {
      games: FileGame[]
      wholeBggCollection: boolean
    }) => {
      const { data, error } = await api.POST('/api/me/games/file-import/preview', {
        body: {
          whole_bgg_collection: wholeBggCollection,
          games: games.map((g) => ({ game_id: g.gameId, values: g.values })),
        },
      })
      if (error) throw new Error(detailOf(error, 'Could not preview these changes'))
      return data
    },
  })
}
