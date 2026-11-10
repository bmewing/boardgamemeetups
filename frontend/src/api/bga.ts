import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { api } from './client'
import type { components } from './schema'

export type BgaLink = components['schemas']['BgaLink']
export type BgaGame = components['schemas']['BgaGameRead']

/** Games on Board Game Arena by name, for nominating at an online date. */
export function useBgaSearch(query: string) {
  const q = query.trim()
  return useQuery({
    queryKey: ['bga', 'search', q],
    enabled: q.length >= 2,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/bga/games', { params: { query: { q } } })
      if (error) throw new Error('Search failed')
      return data
    },
  })
}
