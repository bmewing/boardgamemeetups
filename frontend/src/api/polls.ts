import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import { detailOf } from './collection'
import { groupKey } from './groups'
import type { components } from './schema'

export type Poll = components['schemas']['PollRead']
export type PollBrief = components['schemas']['PollBrief']
export type PollCreate = components['schemas']['PollCreate']
export type PollPerson = components['schemas']['PersonRead']

const pollKey = (id: string) => ['polls', id] as const
const groupPollsKey = (groupId: string) => ['polls', 'group', groupId] as const

/** The group's polls, newest first. */
export function useGroupPolls(groupId: string) {
  return useQuery({
    queryKey: groupPollsKey(groupId),
    queryFn: async () => {
      const { data, error } = await api.GET('/api/groups/{group_id}/polls', {
        params: { path: { group_id: groupId } },
      })
      if (error) throw new Error('Could not load the polls')
      return data.polls
    },
  })
}

/** Null when there's no such poll, or it's in a group you aren't in. Refetches every 15
 *  seconds so other people's answers show up while you're looking. */
export function usePoll(pollId: string) {
  return useQuery({
    queryKey: pollKey(pollId),
    refetchInterval: 15_000,
    queryFn: async () => {
      const { data, error, response } = await api.GET('/api/polls/{poll_id}', {
        params: { path: { poll_id: pollId } },
      })
      if (response.status === 404) return null
      if (error) throw new Error('Could not load the poll')
      return data
    },
  })
}

export function useCreatePoll(groupId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: PollCreate) => {
      const { data, error } = await api.POST('/api/groups/{group_id}/polls', {
        params: { path: { group_id: groupId } },
        body,
      })
      if (error) throw new Error(detailOf(error, 'Could not start the poll'))
      return data
    },
    onSuccess: (poll) => {
      queryClient.setQueryData(pollKey(poll.id), poll)
      return queryClient.invalidateQueries({ queryKey: groupPollsKey(groupId) })
    },
  })
}

/** Saves the whole answer, replacing the earlier one. */
export function useSaveAnswer(pollId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (slots: string[]) => {
      const { data, error } = await api.PUT('/api/polls/{poll_id}/answer', {
        params: { path: { poll_id: pollId } },
        body: { slots },
      })
      if (error) throw new Error(detailOf(error, 'Could not save your times'))
      return data
    },
    onSuccess: (poll) => {
      queryClient.setQueryData(pollKey(poll.id), poll)
      return queryClient.invalidateQueries({ queryKey: groupPollsKey(poll.group_id) })
    },
  })
}

export function useClosePoll(pollId: string) {
  return usePollStatus(pollId, '/api/polls/{poll_id}/close')
}

export function useReopenPoll(pollId: string) {
  return usePollStatus(pollId, '/api/polls/{poll_id}/reopen')
}

function usePollStatus(
  pollId: string,
  path: '/api/polls/{poll_id}/close' | '/api/polls/{poll_id}/reopen',
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST(path, { params: { path: { poll_id: pollId } } })
      if (error) throw new Error(detailOf(error, 'Could not change the poll'))
      return data
    },
    onSuccess: (poll) => {
      queryClient.setQueryData(pollKey(poll.id), poll)
      return queryClient.invalidateQueries({ queryKey: groupPollsKey(poll.group_id) })
    },
  })
}

/** Emails the members who haven't answered. */
export function useRemindPoll(pollId: string) {
  return useMutation({
    mutationFn: async () => {
      const { error } = await api.POST('/api/polls/{poll_id}/remind', {
        params: { path: { poll_id: pollId } },
      })
      if (error) throw new Error(detailOf(error, 'Could not send the reminder'))
    },
  })
}

export function useDeletePoll(pollId: string, groupId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { error } = await api.DELETE('/api/polls/{poll_id}', {
        params: { path: { poll_id: pollId } },
      })
      if (error) throw new Error(detailOf(error, 'Could not delete the poll'))
    },
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: pollKey(pollId) })
      return queryClient.invalidateQueries({ queryKey: groupPollsKey(groupId) })
    },
  })
}

/** Makes a date at one of the poll's times and closes the poll. Resolves to the poll, whose
 *  `meetup_id` is the new date. */
export function useSchedulePoll(pollId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (start: string) => {
      const { data, error } = await api.POST('/api/polls/{poll_id}/schedule', {
        params: { path: { poll_id: pollId } },
        body: { start },
      })
      if (error) throw new Error(detailOf(error, 'Could not schedule that time'))
      return data
    },
    onSuccess: (poll) => {
      queryClient.setQueryData(pollKey(poll.id), poll)
      queryClient.invalidateQueries({ queryKey: groupPollsKey(poll.group_id) })
      return queryClient.invalidateQueries({ queryKey: groupKey(poll.group_id) })
    },
  })
}
