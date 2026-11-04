import type { Schedule } from '../api/groups'

export const WEEKDAY_NAMES = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
]

const NTH_NAMES: Record<number, string> = {
  1: 'first',
  2: 'second',
  3: 'third',
  4: 'fourth',
  [-1]: 'last',
}

/** "2026-11-05" as a calendar date, without the browser's time zone shifting it. */
export function calendarDate(isoDate: string): Date {
  const [y, m, d] = isoDate.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function isoDate(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function todayIso(): string {
  return isoDate(new Date())
}

const shortDate = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  month: 'short',
  day: 'numeric',
})
const longDate = new Intl.DateTimeFormat(undefined, {
  weekday: 'long',
  month: 'long',
  day: 'numeric',
  year: 'numeric',
})
const clock = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' })

export const formatShortDate = (isoDate: string) => shortDate.format(calendarDate(isoDate))
export const formatLongDate = (isoDate: string) => longDate.format(calendarDate(isoDate))

/** "19:00:00" as the reader writes times ("7:00 PM"). */
export function formatTime(localTime: string): string {
  const [h, m] = localTime.split(':').map(Number)
  return clock.format(new Date(2000, 0, 1, h, m))
}

/** The end of a meetup, from its local start and length. */
export function endTime(localTime: string, minutes: number): string {
  const [h, m] = localTime.split(':').map(Number)
  const end = new Date(2000, 0, 1, h, m + minutes)
  return clock.format(end)
}

export function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h === 0) return `${m} min`
  return m ? `${h} h ${m} min` : `${h} h`
}

export function ordinal(n: number): string {
  const tens = n % 100
  if (tens >= 11 && tens <= 13) return `${n}th`
  return `${n}${{ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th'}`
}

export function scheduleLabel(schedule: Schedule | null): string {
  if (!schedule) return 'No regular schedule'
  switch (schedule.kind) {
    case 'weekly': {
      const every = schedule.every_weeks ?? 1
      const day = WEEKDAY_NAMES[schedule.weekday]
      return every === 1 ? `Every ${day}` : `Every ${every} weeks on ${day}`
    }
    case 'monthly_weekday':
      return `The ${NTH_NAMES[schedule.nth]} ${WEEKDAY_NAMES[schedule.weekday]} of each month`
    case 'monthly_day':
      return `The ${ordinal(schedule.day)} of each month`
  }
}

/** "19:00:00" to the "19:00" a time input shows, and back. */
export const toInputTime = (t: string) => t.slice(0, 5)
export const fromInputTime = (t: string) => (t.length === 5 ? `${t}:00` : t)

export const ROLE_LABELS = { owner: 'Owner', admin: 'Admin', member: 'Member' } as const
