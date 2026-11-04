import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import { detailOf } from './collection'
import type { PersonPick } from './friends'
import type { components } from './schema'

export type Groups = components['schemas']['GroupsRead']
export type GroupSummary = components['schemas']['GroupSummary']
export type GroupInviteForMe = components['schemas']['GroupInviteForMe']
export type Group = components['schemas']['GroupRead']
export type GroupUpdate = components['schemas']['GroupUpdate']
export type GroupRole = components['schemas']['GroupRole']
export type Member = components['schemas']['MemberRead']
export type MeetupBrief = components['schemas']['MeetupBrief']
export type Meetup = components['schemas']['MeetupRead']
export type MeetupUpdate = components['schemas']['MeetupUpdate']
export type MeetupCreate = components['schemas']['MeetupCreate']
export type RsvpResponse = components['schemas']['RsvpResponse']
export type MeetupGames = components['schemas']['MeetupGames']
export type GroupGame = components['schemas']['GroupGameRead']
export type Schedule = NonNullable<Group['schedule']>

const GROUPS_KEY = ['groups'] as const
const groupKey = (id: string) => ['groups', id] as const
const meetupKey = (id: string) => ['meetups', id] as const

export const runsGroup = (role: GroupRole) => role === 'owner' || role === 'admin'

export function useGroups() {
  const { isAuthenticated } = useKindeAuth()
  return useQuery({
    queryKey: GROUPS_KEY,
    enabled: isAuthenticated,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/groups')
      if (error) throw new Error('Could not load your groups')
      return data
    },
  })
}

export function useCreateGroup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: components['schemas']['GroupCreate']) => {
      const { data, error } = await api.POST('/api/groups', { body })
      if (error) throw new Error(detailOf(error, 'Could not make the group'))
      return data
    },
    onSuccess: (group) => {
      queryClient.setQueryData(groupKey(group.id), group)
      return queryClient.invalidateQueries({ queryKey: GROUPS_KEY })
    },
  })
}

/** Null when there's no such group, or you aren't in it. */
export function useGroup(groupId: string) {
  return useQuery({
    queryKey: groupKey(groupId),
    queryFn: async () => {
      const { data, error, response } = await api.GET('/api/groups/{group_id}', {
        params: { path: { group_id: groupId } },
      })
      if (response.status === 404 || response.status === 422) return null
      if (error) throw new Error('Could not load this group')
      return data
    },
  })
}

/** Most group changes answer with the whole group; store it and refresh the list. */
function useGroupMutation<T>(groupId: string, send: (input: T) => Promise<Group | undefined>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: send,
    onSuccess: (group) => {
      if (group) queryClient.setQueryData(groupKey(groupId), group)
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: GROUPS_KEY, exact: true }),
        queryClient.invalidateQueries({ queryKey: ['meetups'] }),
        group ? undefined : queryClient.invalidateQueries({ queryKey: groupKey(groupId) }),
      ])
    },
  })
}

export function useUpdateGroup(groupId: string) {
  return useGroupMutation(groupId, async (body: GroupUpdate) => {
    const { data, error } = await api.PATCH('/api/groups/{group_id}', {
      params: { path: { group_id: groupId } },
      body,
    })
    if (error) throw new Error(detailOf(error, 'Could not save the group'))
    return data
  })
}

export function useDeleteGroup(groupId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { error } = await api.DELETE('/api/groups/{group_id}', {
        params: { path: { group_id: groupId } },
      })
      if (error) throw new Error(detailOf(error, 'Could not delete the group'))
    },
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: groupKey(groupId) })
      return queryClient.invalidateQueries({ queryKey: GROUPS_KEY })
    },
  })
}

export function useInviteToGroup(groupId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (pick: PersonPick) => {
      const { data, error } = await api.POST('/api/groups/{group_id}/invites', {
        params: { path: { group_id: groupId } },
        body: pick,
      })
      if (error) throw new Error(detailOf(error, 'Could not send the invite'))
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: groupKey(groupId) }),
  })
}

export function useCancelGroupInvite(groupId: string) {
  return useGroupMutation(groupId, async (inviteId: string) => {
    const { error } = await api.DELETE('/api/groups/{group_id}/invites/{invite_id}', {
      params: { path: { group_id: groupId, invite_id: inviteId } },
    })
    if (error) throw new Error('Could not cancel the invite')
    return undefined
  })
}

export function useAnswerGroupInvite() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ inviteId, accept }: { inviteId: string; accept: boolean }) => {
      const path = { params: { path: { invite_id: inviteId } } }
      if (accept) {
        const { data, error } = await api.POST('/api/group-invites/{invite_id}/accept', path)
        if (error) throw new Error(detailOf(error, 'Could not join the group'))
        return data
      }
      const { error } = await api.POST('/api/group-invites/{invite_id}/decline', path)
      if (error) throw new Error('Could not decline the invite')
      return undefined
    },
    onSuccess: (group) => {
      if (group) queryClient.setQueryData(groupKey(group.id), group)
      return queryClient.invalidateQueries({ queryKey: GROUPS_KEY })
    },
  })
}

export function useChangeRole(groupId: string) {
  return useGroupMutation(
    groupId,
    async ({ userId, role }: { userId: string; role: GroupRole }) => {
      const { data, error } = await api.PATCH('/api/groups/{group_id}/members/{user_id}', {
        params: { path: { group_id: groupId, user_id: userId } },
        body: { role },
      })
      if (error) throw new Error(detailOf(error, 'Could not change their role'))
      return data
    },
  )
}

/** Remove someone, or leave (your own id). */
export function useRemoveMember(groupId: string) {
  return useGroupMutation(groupId, async (userId: string) => {
    const { error } = await api.DELETE('/api/groups/{group_id}/members/{user_id}', {
      params: { path: { group_id: groupId, user_id: userId } },
    })
    if (error) throw new Error(detailOf(error, 'Could not do that'))
    return undefined
  })
}

export function useGroupGames(groupId: string, enabled = true) {
  return useQuery({
    queryKey: [...groupKey(groupId), 'games'],
    enabled,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/groups/{group_id}/games', {
        params: { path: { group_id: groupId } },
      })
      if (error) throw new Error("Could not load the group's games")
      return data
    },
  })
}

export function useAddMeetup(groupId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: MeetupCreate) => {
      const { data, error } = await api.POST('/api/groups/{group_id}/meetups', {
        params: { path: { group_id: groupId } },
        body,
      })
      if (error) throw new Error(detailOf(error, 'Could not add the date'))
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: groupKey(groupId) }),
  })
}

/** Null when there's no such meetup, or it's in a group you aren't in. */
export function useMeetup(meetupId: string) {
  return useQuery({
    queryKey: meetupKey(meetupId),
    queryFn: async () => {
      const { data, error, response } = await api.GET('/api/meetups/{meetup_id}', {
        params: { path: { meetup_id: meetupId } },
      })
      if (response.status === 404 || response.status === 422) return null
      if (error) throw new Error('Could not load this date')
      return data
    },
  })
}

function useMeetupMutation<T>(meetupId: string, send: (input: T) => Promise<Meetup>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: send,
    onSuccess: (meetup) => {
      queryClient.setQueryData(meetupKey(meetupId), meetup)
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: [...meetupKey(meetupId), 'games'] }),
        queryClient.invalidateQueries({ queryKey: groupKey(meetup.group.id) }),
        queryClient.invalidateQueries({ queryKey: GROUPS_KEY, exact: true }),
      ])
    },
  })
}

export function useRsvp(meetupId: string) {
  return useMeetupMutation(meetupId, async (response: RsvpResponse) => {
    const { data, error } = await api.PUT('/api/meetups/{meetup_id}/rsvp', {
      params: { path: { meetup_id: meetupId } },
      body: { response },
    })
    if (error) throw new Error(detailOf(error, 'Could not save your answer'))
    return data
  })
}

export function useUpdateMeetup(meetupId: string) {
  return useMeetupMutation(meetupId, async (body: MeetupUpdate) => {
    const { data, error } = await api.PATCH('/api/meetups/{meetup_id}', {
      params: { path: { meetup_id: meetupId } },
      body,
    })
    if (error) throw new Error(detailOf(error, 'Could not save this date'))
    return data
  })
}

export function useDeleteMeetup(meetupId: string, groupId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { error } = await api.DELETE('/api/meetups/{meetup_id}', {
        params: { path: { meetup_id: meetupId } },
      })
      if (error) throw new Error(detailOf(error, 'Could not remove this date'))
    },
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: meetupKey(meetupId) })
      return queryClient.invalidateQueries({ queryKey: groupKey(groupId) })
    },
  })
}

export function useMeetupGames(meetupId: string) {
  return useQuery({
    queryKey: [...meetupKey(meetupId), 'games'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/meetups/{meetup_id}/games', {
        params: { path: { meetup_id: meetupId } },
      })
      if (error) throw new Error('Could not load the games')
      return data
    },
  })
}
