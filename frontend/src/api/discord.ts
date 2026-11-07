import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import { detailOf } from './collection'
import { ME_KEY } from './me'

/** Which Discord account a link from the bot is for. Needs no sign-in. */
export function useDiscordLink(token: string) {
  return useQuery({
    queryKey: ['discord-link', token],
    retry: false,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/discord/link/{token}', {
        params: { path: { token } },
      })
      if (error !== undefined || !data) throw new Error(detailOf(error, 'This link has expired.'))
      return data
    },
  })
}

export function useLinkDiscord() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (token: string) => {
      const { data, error } = await api.PUT('/api/me/discord', { body: { token } })
      if (error !== undefined || !data)
        throw new Error(detailOf(error, "Couldn't link your Discord account. Try again."))
      return data
    },
    onSuccess: (profile) => queryClient.setQueryData(ME_KEY, profile),
  })
}

export function useUnlinkDiscord() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await api.DELETE('/api/me/discord')
      if (error !== undefined || !data) throw new Error("Couldn't unlink Discord. Try again.")
      return data
    },
    onSuccess: (profile) => queryClient.setQueryData(ME_KEY, profile),
  })
}
