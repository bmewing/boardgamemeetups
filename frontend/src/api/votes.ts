import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import { detailOf } from './collection'
import type { components } from './schema'

export type VoteState = components['schemas']['VoteRead']
export type Nomination = components['schemas']['NominationRead']
export type PlayLog = components['schemas']['LogRead']
export type PlayLogIn = components['schemas']['LogIn']
export type PlayIn = components['schemas']['PlayIn']

const voteKey = (meetupId: string) => ['meetups', meetupId, 'vote'] as const
const logKey = (meetupId: string) => ['meetups', meetupId, 'log'] as const
// The function can't push updates, so an open vote is refreshed this often.
const TALLY_REFRESH_MS = 5000

export function useVote(meetupId: string) {
  return useQuery({
    queryKey: voteKey(meetupId),
    queryFn: async () => {
      const { data, error } = await api.GET('/api/meetups/{meetup_id}/vote', {
        params: { path: { meetup_id: meetupId } },
      })
      if (error) throw new Error('Could not load the vote')
      return data
    },
    refetchInterval: (query) => (query.state.data?.locked ? false : TALLY_REFRESH_MS),
  })
}

/** Every vote change answers with the whole vote; store it, and refresh the picks' games. */
function useVoteMutation<T>(meetupId: string, send: (input: T) => Promise<VoteState>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: send,
    onSuccess: (state) => queryClient.setQueryData(voteKey(meetupId), state),
  })
}

const path = (meetupId: string) => ({ params: { path: { meetup_id: meetupId } } })

export function useNominate(meetupId: string) {
  return useVoteMutation(meetupId, async (gameId: number) => {
    const { data, error } = await api.POST('/api/meetups/{meetup_id}/nominations', {
      ...path(meetupId),
      body: { game_id: gameId },
    })
    if (error) throw new Error(detailOf(error, 'Could not nominate it'))
    return data
  })
}

export function useWithdraw(meetupId: string) {
  return useVoteMutation(meetupId, async (nominationId: string) => {
    const { data, error } = await api.DELETE(
      '/api/meetups/{meetup_id}/nominations/{nomination_id}',
      { params: { path: { meetup_id: meetupId, nomination_id: nominationId } } },
    )
    if (error) throw new Error(detailOf(error, 'Could not take it off'))
    return data
  })
}

export function useCastVote(meetupId: string) {
  return useVoteMutation(
    meetupId,
    async ({ nominationId, on }: { nominationId: string; on: boolean }) => {
      const options = { params: { path: { meetup_id: meetupId, nomination_id: nominationId } } }
      const url = '/api/meetups/{meetup_id}/nominations/{nomination_id}/vote' as const
      const { data, error } = on ? await api.PUT(url, options) : await api.DELETE(url, options)
      if (error) throw new Error(detailOf(error, 'Could not save your vote'))
      return data
    },
  )
}

export function useLockPick(meetupId: string) {
  return useVoteMutation(meetupId, async (nominationIds: string[]) => {
    const { data, error } = await api.POST('/api/meetups/{meetup_id}/lock', {
      ...path(meetupId),
      body: { nomination_ids: nominationIds },
    })
    if (error) throw new Error(detailOf(error, 'Could not lock the pick'))
    return data
  })
}

export function useUnlockPick(meetupId: string) {
  return useVoteMutation(meetupId, async () => {
    const { data, error } = await api.POST('/api/meetups/{meetup_id}/unlock', path(meetupId))
    if (error) throw new Error(detailOf(error, 'Could not unlock it'))
    return data
  })
}

/** Bring a picked game: yourself with no user, or hand it to someone (owner or admin). */
export function useBring(meetupId: string) {
  return useVoteMutation(
    meetupId,
    async ({ gameId, userId, stop }: { gameId: number; userId?: string; stop?: boolean }) => {
      const options = { params: { path: { meetup_id: meetupId, game_id: gameId } } }
      const url = '/api/meetups/{meetup_id}/bring/{game_id}' as const
      const { data, error } = stop
        ? await api.DELETE(url, options)
        : await api.PUT(url, { ...options, body: { user_id: userId ?? null } })
      if (error) throw new Error(detailOf(error, 'Could not change who brings it'))
      return data
    },
  )
}

export function usePlayLog(meetupId: string, enabled: boolean) {
  return useQuery({
    queryKey: logKey(meetupId),
    enabled,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/meetups/{meetup_id}/log', path(meetupId))
      if (error) throw new Error('Could not load what was played')
      return data
    },
  })
}

export function useSavePlayLog(meetupId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: PlayLogIn) => {
      const { data, error } = await api.PUT('/api/meetups/{meetup_id}/log', {
        ...path(meetupId),
        body,
      })
      if (error) throw new Error(detailOf(error, 'Could not save what was played'))
      return data
    },
    onSuccess: (log) => queryClient.setQueryData(logKey(meetupId), log),
  })
}
