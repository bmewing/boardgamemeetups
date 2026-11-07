import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import { detailOf, MY_GAMES_KEY } from './collection'
import type { components } from './schema'

export type GameSummary = components['schemas']['GameSummary']
export type GameDetail = components['schemas']['GameDetail']
export type CustomGameIn = components['schemas']['CustomGameIn']

export function useGameSearch(query: string) {
  const q = query.trim()
  return useQuery({
    queryKey: ['games', 'search', q],
    enabled: q.length >= 2,
    // Keep showing the last results while the next search loads.
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/games/search', { params: { query: { q } } })
      if (error) throw new Error('Search failed')
      return data
    },
  })
}

export function useGame(gameId: number) {
  return useQuery({
    queryKey: ['games', gameId],
    enabled: Number.isInteger(gameId),
    queryFn: async () => {
      const { data, error, response } = await api.GET('/api/games/{game_id}', {
        params: { path: { game_id: gameId } },
      })
      if (response.status === 404) throw new Error('No such game')
      if (error) throw new Error('Could not load this game')
      return data
    },
  })
}

/** Add a game that isn't on BGG. It lands in your list as owned. */
export function useAddCustomGame() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (game: CustomGameIn) => {
      const { data, error } = await api.POST('/api/games', { body: game })
      if (error) throw new Error(detailOf(error, 'Could not add this game'))
      return data
    },
    onSuccess: (game) => {
      queryClient.setQueryData(['games', game.id], game)
      return queryClient.invalidateQueries({ queryKey: MY_GAMES_KEY })
    },
  })
}

/** Change a game you added. */
export function useUpdateCustomGame(gameId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (game: CustomGameIn) => {
      const { data, error } = await api.PUT('/api/games/{game_id}', {
        params: { path: { game_id: gameId } },
        body: game,
      })
      if (error) throw new Error(detailOf(error, 'Could not save this game'))
      return data
    },
    onSuccess: (game) => {
      queryClient.setQueryData(['games', game.id], game)
      return queryClient.invalidateQueries({ queryKey: MY_GAMES_KEY })
    },
  })
}
