import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, type UserProfileUpdate } from './client'
import { detailOf } from './collection'

export const ME_KEY = ['me'] as const

/** The API refuses every request from a banned account with a 403. */
export class AccountSuspendedError extends Error {}

export function useMe() {
  const { isAuthenticated } = useKindeAuth()
  return useQuery({
    queryKey: ME_KEY,
    enabled: isAuthenticated,
    retry: (failures, error) => !(error instanceof AccountSuspendedError) && failures < 3,
    queryFn: async () => {
      const { data, error, response } = await api.GET('/api/me')
      if (response.status === 403) {
        throw new AccountSuspendedError(detailOf(error, 'This account has been suspended.'))
      }
      if (error) throw new Error('Could not load your profile')
      return data
    },
  })
}

export function useUpdateMe() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (changes: UserProfileUpdate) => {
      const { data, error } = await api.PATCH('/api/me', { body: changes })
      if (error) throw new Error(detailOf(error, 'Could not save your profile'))
      return data
    },
    onSuccess: (profile) => queryClient.setQueryData(ME_KEY, profile),
  })
}

export function useDeleteMe() {
  return useMutation({
    mutationFn: async () => {
      const { error } = await api.DELETE('/api/me')
      if (error) throw new Error('Could not delete your account')
    },
  })
}
