import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import { detailOf } from './collection'
import type { components } from './schema'

export type Person = components['schemas']['PersonRead']
export type Friend = components['schemas']['FriendRead']
export type Friends = components['schemas']['FriendsRead']
export type Relation = components['schemas']['Relation']
export type PersonProfile = components['schemas']['PersonProfile']
export type SharedGame = components['schemas']['SharedGameRead']
export type InviteLink = components['schemas']['InviteLinkRead']
export type PersonPick = components['schemas']['PersonPick']
export type PersonMatch = components['schemas']['PersonMatch']

const FRIENDS_KEY = ['friends'] as const
const BLOCKS_KEY = ['blocks'] as const
const LINKS_KEY = ['invite-links'] as const
const PEOPLE_KEY = ['people'] as const

/** An invite link's full address, as it would be shared. */
export function inviteUrl(token: string) {
  return `${window.location.origin}/invite/${token}`
}

export function useFriends() {
  const { isAuthenticated } = useKindeAuth()
  return useQuery({
    queryKey: FRIENDS_KEY,
    enabled: isAuthenticated,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/friends')
      if (error) throw new Error('Could not load your friends')
      return data
    },
  })
}

/** After any change between you and someone else: lists and their page both refresh. */
function useRefreshFriends() {
  const queryClient = useQueryClient()
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: FRIENDS_KEY }),
      queryClient.invalidateQueries({ queryKey: BLOCKS_KEY }),
      queryClient.invalidateQueries({ queryKey: PEOPLE_KEY }),
    ])
}

export function useSendFriendRequest() {
  const refresh = useRefreshFriends()
  return useMutation({
    mutationFn: async (pick: PersonPick) => {
      const { data, error, response } = await api.POST('/api/friends/requests', { body: pick })
      if (error) {
        throw new FriendRequestError(
          detailOf(error, 'Could not send the request'),
          response.status === 404,
        )
      }
      return data
    },
    onSuccess: refresh,
  })
}

/** Suggestions as you type a name (or a full email). Empty until 2 letters are typed. */
export function usePeopleSearch(query: string) {
  const q = query.trim()
  return useQuery({
    queryKey: ['people', 'search', q],
    enabled: q.length >= 2,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/people/search', { params: { query: { q } } })
      if (error) throw new Error('Search failed')
      return data
    },
  })
}

export class FriendRequestError extends Error {
  /** Nobody here uses that email, so an invite link is the way to reach them. */
  readonly notFound: boolean

  constructor(message: string, notFound: boolean) {
    super(message)
    this.notFound = notFound
  }
}

type Answer = 'accept' | 'decline' | 'remove' | 'block' | 'unblock'

/** Everything you can do about someone else, in one place. */
export function useFriendAction() {
  const refresh = useRefreshFriends()
  return useMutation({
    mutationFn: async ({ userId, action }: { userId: string; action: Answer }) => {
      const path = { params: { path: { user_id: userId } } }
      const { error } = await (() => {
        switch (action) {
          case 'accept':
            return api.POST('/api/friends/{user_id}/accept', path)
          case 'decline':
            return api.POST('/api/friends/{user_id}/decline', path)
          case 'remove':
            return api.DELETE('/api/friends/{user_id}', path)
          case 'block':
            return api.PUT('/api/blocks/{user_id}', path)
          case 'unblock':
            return api.DELETE('/api/blocks/{user_id}', path)
        }
      })()
      if (error) throw new Error(detailOf(error, 'Could not do that just now'))
    },
    onSuccess: refresh,
  })
}

export function useBlocks() {
  return useQuery({
    queryKey: BLOCKS_KEY,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/blocks')
      if (error) throw new Error('Could not load blocked people')
      return data
    },
  })
}

export function useInviteLinks() {
  return useQuery({
    queryKey: LINKS_KEY,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/invite-links')
      if (error) throw new Error('Could not load your invite links')
      return data
    },
  })
}

export function useCreateInviteLink() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST('/api/invite-links')
      if (error) throw new Error(detailOf(error, 'Could not make a link'))
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: LINKS_KEY }),
  })
}

export function useTurnOffInviteLink() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (linkId: string) => {
      const { error } = await api.DELETE('/api/invite-links/{link_id}', {
        params: { path: { link_id: linkId } },
      })
      if (error) throw new Error('Could not turn off this link')
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: LINKS_KEY }),
  })
}

/** Who sent an invite link. Works signed out too. Null when the link is no good. */
export function useInvite(token: string) {
  return useQuery({
    queryKey: ['invites', token],
    queryFn: async () => {
      const { data, error, response } = await api.GET('/api/invites/{token}', {
        params: { path: { token } },
      })
      if (response.status === 404) return null
      if (error) throw new Error('Could not open this invite')
      return data
    },
  })
}

export function useAcceptInvite() {
  const refresh = useRefreshFriends()
  return useMutation({
    mutationFn: async (token: string) => {
      const { data, error } = await api.POST('/api/invites/{token}/accept', {
        params: { path: { token } },
      })
      if (error) throw new Error(detailOf(error, 'Could not accept this invite'))
      return data
    },
    onSuccess: refresh,
  })
}

/** Their name and how you stand; null when there's no such person (or a block between you). */
export function usePerson(userId: string) {
  return useQuery({
    queryKey: [...PEOPLE_KEY, userId],
    queryFn: async () => {
      const { data, error, response } = await api.GET('/api/people/{user_id}', {
        params: { path: { user_id: userId } },
      })
      if (response.status === 404 || response.status === 422) return null
      if (error) throw new Error('Could not load this person')
      return data
    },
  })
}

export function usePersonGames(userId: string, enabled: boolean) {
  return useQuery({
    queryKey: [...PEOPLE_KEY, userId, 'games'],
    enabled,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/people/{user_id}/games', {
        params: { path: { user_id: userId } },
      })
      if (error) throw new Error(detailOf(error, 'Could not load their games'))
      return data
    },
  })
}
