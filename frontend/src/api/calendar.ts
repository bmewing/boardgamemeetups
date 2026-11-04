import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import type { components } from './schema'

export type CalendarFeed = components['schemas']['CalendarFeedRead']

const FEED_KEY = ['calendar-feed'] as const

/** The feed's address, for pasting into a calendar app. It needs no sign-in. */
export function feedUrl(token: string) {
  return `${window.location.origin}${import.meta.env.VITE_API_BASE ?? ''}/api/calendar/${token}.ics`
}

/** The same address with webcal://, which opens the device's calendar app to subscribe. */
export function webcalUrl(token: string) {
  return feedUrl(token).replace(/^https?:/, 'webcal:')
}

export function googleSubscribeUrl(token: string) {
  return `https://calendar.google.com/calendar/render?cid=${encodeURIComponent(webcalUrl(token))}`
}

/** Null when you have no feed, or turned it off. */
export function useCalendarFeed() {
  const { isAuthenticated } = useKindeAuth()
  return useQuery({
    queryKey: FEED_KEY,
    enabled: isAuthenticated,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/me/calendar-feed')
      if (error) throw new Error('Could not load your calendar link')
      return data ?? null
    },
  })
}

/** Makes a new link; any old one stops working. */
export function useMakeCalendarFeed() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST('/api/me/calendar-feed')
      if (error) throw new Error('Could not make a calendar link')
      return data
    },
    onSuccess: (feed) => queryClient.setQueryData(FEED_KEY, feed),
  })
}

export function useTurnOffCalendarFeed() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { error } = await api.DELETE('/api/me/calendar-feed')
      if (error) throw new Error('Could not turn off the calendar link')
    },
    onSuccess: () => queryClient.setQueryData(FEED_KEY, null),
  })
}
