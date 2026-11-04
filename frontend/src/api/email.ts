import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import type { components } from './schema'

export type EmailKind = components['schemas']['EmailKind']

/** Every kind of email, in the order the profile page lists them. */
export const EMAIL_KINDS: {
  kind: EmailKind
  label: string
  description: string
  /** Follows "emails about", as in each email's unsubscribe link. */
  about: string
}[] = [
  {
    kind: 'rsvp_reminder',
    label: 'Reminders',
    description: "The day before a date you haven't answered or said maybe to.",
    about: "dates you haven't answered",
  },
  {
    kind: 'date_changed',
    label: 'Date changes',
    description:
      "When a date you might go to moves, changes place or is cancelled, or a group's schedule changes.",
    about: 'dates that change or are cancelled',
  },
  {
    kind: 'pick_locked',
    label: 'Games picked',
    description: 'When the games are locked in for a date you said yes or maybe to.',
    about: 'the games picked for a date',
  },
  {
    kind: 'bringing',
    label: "Games you're bringing",
    description: 'When someone asks you to bring a game, or a picked game is yours to bring.',
    about: "games you're bringing",
  },
  {
    kind: 'group_invite',
    label: 'Group invites',
    description: "When you're invited to a group.",
    about: 'group invites',
  },
  {
    kind: 'friend_request',
    label: 'Friend requests',
    description: 'When someone asks to be your friend.',
    about: 'friend requests',
  },
]

export function emailKind(value: string | null): (typeof EMAIL_KINDS)[number] | undefined {
  return EMAIL_KINDS.find((k) => k.kind === value)
}

const settingsKey = (token: string) => ['email-settings', token] as const

/** What the owner of an email's unsubscribe link has turned off. Needs no sign-in. */
export function useEmailSettingsByLink(token: string) {
  return useQuery({
    queryKey: settingsKey(token),
    retry: false,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/email/unsubscribe/{token}', {
        params: { path: { token } },
      })
      if (error) throw new Error("This link doesn't work any more.")
      return data
    },
  })
}

/** Turn off one kind of email, or every kind when none is given. */
export function useUnsubscribe(token: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (kind: EmailKind | null) => {
      const { data, error } = await api.POST('/api/email/unsubscribe/{token}', {
        params: { path: { token }, query: kind ? { kind } : {} },
      })
      if (error) throw new Error("Couldn't change your email settings. Try again.")
      return data
    },
    onSuccess: (settings) => queryClient.setQueryData(settingsKey(token), settings),
  })
}
