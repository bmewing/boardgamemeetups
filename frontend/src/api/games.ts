import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { api } from './client'
import type { components } from './schema'

export type GameSummary = components['schemas']['GameSummary']
export type GameDetail = components['schemas']['GameDetail']

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
      if (response.status === 404) throw new Error('No such game on BoardGameGeek')
      if (error) throw new Error('Could not load this game')
      return data
    },
  })
}
