import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import { api } from './client'
import type { components } from './schema'

export type UserGame = components['schemas']['UserGameRead']
export type UserGameUpdate = components['schemas']['UserGameUpdate']
export type Ownership = components['schemas']['Ownership']
export type ImportPreview = components['schemas']['ImportPreview']
export type GameDiff = components['schemas']['GameDiffRead']
export type FieldChange = components['schemas']['FieldChangeRead']
export type FieldName = FieldChange['field']
export type ChangeIn = components['schemas']['ChangeIn']
export type ImportResult = components['schemas']['ImportResult']
export type ImportSource = components['schemas']['ImportApply']['source']

const MY_GAMES_KEY = ['me', 'games'] as const

/** The API's own explanation (FastAPI's `detail`), when it sent a plain one. */
export function detailOf(error: unknown, fallback: string): string {
  if (error && typeof error === 'object' && 'detail' in error) {
    const { detail } = error as { detail: unknown }
    if (typeof detail === 'string') return detail
  }
  return fallback
}

export function useMyGames() {
  return useQuery({
    queryKey: MY_GAMES_KEY,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/me/games')
      if (error) throw new Error('Could not load your games')
      return data
    },
  })
}

export function useUpdateMyGame() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ gameId, changes }: { gameId: number; changes: UserGameUpdate }) => {
      const { data, error } = await api.PUT('/api/me/games/{game_id}', {
        params: { path: { game_id: gameId } },
        body: changes,
      })
      if (error) throw new Error(detailOf(error, 'Could not save this game'))
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: MY_GAMES_KEY }),
  })
}

export function useRemoveMyGame() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      gameId,
      expansionIds = [],
    }: {
      gameId: number
      expansionIds?: number[]
    }) => {
      const { error } = await api.DELETE('/api/me/games/{game_id}', {
        params: { path: { game_id: gameId }, query: { expansions: expansionIds } },
      })
      if (error) throw new Error('Could not remove this game')
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: MY_GAMES_KEY }),
  })
}

/** Fetch the BGG collection and list what pulling it would change. Writes nothing. */
export function useBggPullPreview() {
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST('/api/me/games/bgg-pull')
      if (error) throw new Error(detailOf(error, 'Could not reach BoardGameGeek'))
      return data
    },
  })
}

export function useApplyImport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ changes, source }: { changes: ChangeIn[]; source: ImportSource }) => {
      const { data, error } = await api.POST('/api/me/games/import', {
        body: { source, changes },
      })
      if (error) throw new Error(detailOf(error, 'Could not apply these changes'))
      return data
    },
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: MY_GAMES_KEY }),
        queryClient.invalidateQueries({ queryKey: ['me'], exact: true }),
      ]),
  })
}

/** Ask the API to fetch BGG details for a batch of the user's games that lack them. */
export async function fillMyGameDetails() {
  const { data, error } = await api.POST('/api/me/games/fill-details')
  if (error) throw new Error('Could not fetch game details')
  return data
}

export function useInvalidateMyGames() {
  const queryClient = useQueryClient()
  return useCallback(() => queryClient.invalidateQueries({ queryKey: MY_GAMES_KEY }), [queryClient])
}

export type MissingBaseGames = components['schemas']['MissingBaseGamesRead']
export type BaseGameSuggestion = components['schemas']['BaseGameSuggestion']
export type BaseGameChoice = components['schemas']['BaseGameChoice']

/**
 * Base games of the user's owned expansions that they don't own. Each call looks up a batch
 * of unchecked expansions on BGG, so this asks again while that makes progress.
 */
export async function findMissingBaseGames(): Promise<MissingBaseGames> {
  let previous = Infinity
  for (;;) {
    const { data, error } = await api.POST('/api/me/games/missing-base-games')
    if (error) throw new Error(detailOf(error, 'Could not check your expansions'))
    if (data.unchecked === 0 || data.unchecked >= previous) return data
    previous = data.unchecked
  }
}
