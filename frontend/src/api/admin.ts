import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useMe } from './me'
import { api } from './client'
import { detailOf } from './collection'
import type { components } from './schema'

export type AdminStats = components['schemas']['StatsRead']
export type AdminUser = components['schemas']['AdminUserRead']
export type AdminUserPage = components['schemas']['AdminUserPage']
export type AdminUserFilter = 'all' | 'banned' | 'admins'

const ADMIN_KEY = ['admin'] as const
export const ADMIN_PAGE_SIZE = 50

/** Admin queries only run for admins, so nobody else even asks. */
function useIsAdmin() {
  return useMe().data?.is_admin === true
}

export function useAdminStats() {
  const isAdmin = useIsAdmin()
  return useQuery({
    queryKey: [...ADMIN_KEY, 'stats'],
    enabled: isAdmin,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/admin/stats')
      if (error) throw new Error(detailOf(error, 'Could not load the stats'))
      return data
    },
  })
}

export function useAdminUsers(q: string, show: AdminUserFilter, page: number) {
  const isAdmin = useIsAdmin()
  return useQuery({
    queryKey: [...ADMIN_KEY, 'users', { q, show, page }],
    enabled: isAdmin,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/admin/users', {
        params: { query: { q, show, offset: page * ADMIN_PAGE_SIZE, limit: ADMIN_PAGE_SIZE } },
      })
      if (error) throw new Error(detailOf(error, 'Could not load the users'))
      return data
    },
  })
}

/** After any change to an account, both the list and the stats are stale. */
function useAdminMutation<Vars>(run: (vars: Vars) => Promise<unknown>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: run,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_KEY }),
  })
}

export function useBanUser() {
  return useAdminMutation(async ({ userId, reason }: { userId: string; reason: string }) => {
    const { error } = await api.PUT('/api/admin/users/{user_id}/ban', {
      params: { path: { user_id: userId } },
      body: { reason },
    })
    if (error) throw new Error(detailOf(error, 'Could not ban them'))
  })
}

export function useUnbanUser() {
  return useAdminMutation(async (userId: string) => {
    const { error } = await api.DELETE('/api/admin/users/{user_id}/ban', {
      params: { path: { user_id: userId } },
    })
    if (error) throw new Error(detailOf(error, 'Could not lift the ban'))
  })
}

export function useSetAdmin() {
  return useAdminMutation(async ({ userId, isAdmin }: { userId: string; isAdmin: boolean }) => {
    const { error } = await api.PATCH('/api/admin/users/{user_id}', {
      params: { path: { user_id: userId } },
      body: { is_admin: isAdmin },
    })
    if (error) throw new Error(detailOf(error, 'Could not change their role'))
  })
}

export function useDeleteUser() {
  return useAdminMutation(async (userId: string) => {
    const { error } = await api.DELETE('/api/admin/users/{user_id}', {
      params: { path: { user_id: userId } },
    })
    if (error) throw new Error(detailOf(error, 'Could not delete the account'))
  })
}
