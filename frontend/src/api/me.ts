import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, type UserProfileUpdate } from './client'

const ME_KEY = ['me'] as const

export function useMe() {
  const { isAuthenticated } = useKindeAuth()
  return useQuery({
    queryKey: ME_KEY,
    enabled: isAuthenticated,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/me')
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
      if (error) throw new Error('Could not save your profile')
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
