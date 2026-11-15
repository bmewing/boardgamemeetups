/** Slot names are wall-clock times in the poll's zone ("2026-11-19T19:00"), so they're
 *  formatted from their parts as UTC, which never shifts them. */

import { calendarDate, isoDate } from '../meetupFormat'

export const SLOT_MINUTES = 30
const MAX_DAYS = 62

const dayFormat = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  month: 'short',
  day: 'numeric',
  timeZone: 'UTC',
})
const timeFormat = new Intl.DateTimeFormat(undefined, {
  hour: 'numeric',
  minute: '2-digit',
  timeZone: 'UTC',
})

/** "2026-11-19" as "Thu, Nov 19". */
export function dayLabel(isoDate: string): string {
  const [y, m, d] = isoDate.split('-').map(Number)
  return dayFormat.format(new Date(Date.UTC(y, m - 1, d)))
}

/** "19:00" or "2026-11-19T19:00" as "7:00 PM". "24:00" is midnight. */
export function timeLabel(value: string): string {
  const hhmm = value.includes('T') ? value.split('T')[1] : value
  const [h, m] = hhmm.split(':').map(Number)
  return timeFormat.format(new Date(Date.UTC(2000, 0, 1, h % 24, m)))
}

/** "Thu, Nov 19 · 7:00 PM–9:00 PM". */
export function stretchLabel(start: string, end: string): string {
  return `${dayLabel(start.split('T')[0])} · ${timeLabel(start)}–${timeLabel(end)}`
}

/** Every half hour of the day as "HH:MM", for the window pickers. */
export function halfHours(): string[] {
  return Array.from({ length: 48 }, (_, i) => {
    const minute = i * SLOT_MINUTES
    return `${String(Math.floor(minute / 60)).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')}`
  })
}

export function namesOf(people: { display_name: string }[]): string {
  return people.map((p) => p.display_name).join(', ')
}

export function addDays(date: Date, days: number): Date {
  const next = new Date(date)
  next.setDate(next.getDate() + days)
  return next
}

/** Each date from `from` to `to` (inclusive) that falls on one of the chosen weekdays. */
export function datesBetween(from: string, to: string, weekdays: number[]): string[] {
  if (!from || !to) return []
  const dates: string[] = []
  const end = calendarDate(to)
  for (let d = calendarDate(from); d <= end && dates.length <= MAX_DAYS; d = addDays(d, 1)) {
    if (weekdays.includes(d.getDay())) dates.push(isoDate(d))
  }
  return dates
}
