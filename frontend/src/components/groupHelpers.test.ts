import { describe, expect, it } from 'vitest'

import {
  formatDuration,
  googleCalendarUrl,
  ordinal,
  pickMoods,
  scheduleLabel,
  withGuests,
} from './meetupFormat'
import { tableFit } from './tableFit'

describe('tableFit', () => {
  it('matches the API: one table of everyone, or tables that leave nobody alone', () => {
    expect(tableFit(2, 4, 3, false)).toBe('together')
    expect(tableFit(2, 4, 5, false)).toBeNull()
    expect(tableFit(2, 4, 5, true)).toBe('split')
    expect(tableFit(4, 4, 5, true)).toBeNull() // 4 of 5 leaves one alone
    expect(tableFit(4, 4, 6, true)).toBe('split')
    expect(tableFit(null, 4, 3, false)).toBe('together')
    expect(tableFit(2, null, 3, true)).toBeNull()
  })
})

describe('scheduleLabel', () => {
  it('says how often a group meets', () => {
    expect(scheduleLabel(null)).toBe('No regular schedule')
    expect(
      scheduleLabel({ kind: 'weekly', every_weeks: 1, weekday: 3, starts_on: '2026-11-05' }),
    ).toBe('Every Thursday')
    expect(
      scheduleLabel({ kind: 'weekly', every_weeks: 2, weekday: 0, starts_on: '2026-11-02' }),
    ).toBe('Every 2 weeks on Monday')
    expect(
      scheduleLabel({ kind: 'monthly_weekday', nth: -1, weekday: 4, starts_on: '2026-11-01' }),
    ).toBe('The last Friday of each month')
    expect(scheduleLabel({ kind: 'monthly_day', day: 12, starts_on: '2026-11-01' })).toBe(
      'The 12th of each month',
    )
  })

  it('writes ordinals and lengths', () => {
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22, 31].map(ordinal)).toEqual([
      '1st',
      '2nd',
      '3rd',
      '4th',
      '11th',
      '12th',
      '13th',
      '21st',
      '22nd',
      '31st',
    ])
    expect(formatDuration(180)).toBe('3 h')
    expect(formatDuration(150)).toBe('2 h 30 min')
    expect(formatDuration(45)).toBe('45 min')
  })
})

describe('pickMoods', () => {
  it('keeps No preference on its own', () => {
    expect(pickMoods([], ['chill'])).toEqual(['chill'])
    expect(pickMoods(['chill'], ['chill', 'no_preference'])).toEqual(['no_preference'])
    expect(pickMoods(['no_preference'], ['no_preference', 'brain'])).toEqual(['brain'])
    expect(pickMoods(['chill', 'brain'], ['brain'])).toEqual(['brain'])
  })
})

describe('withGuests', () => {
  it('adds guests to a headcount only when there are some', () => {
    expect(withGuests('Going', 3, 0)).toBe('Going (3)')
    expect(withGuests('Going', 3, 1)).toBe('Going (3 + 1 guest)')
    expect(withGuests('Maybe', 1, 2)).toBe('Maybe (1 + 2 guests)')
  })
})

describe('googleCalendarUrl', () => {
  it('fills in the date in UTC', () => {
    const url = new URL(
      googleCalendarUrl({
        title: 'Thursday Crew',
        starts_at: '2026-11-06T01:00:00Z',
        duration_minutes: 180,
        location: '12 Elm St',
        notes: null,
      }),
    )
    expect(url.searchParams.get('text')).toBe('Thursday Crew')
    expect(url.searchParams.get('dates')).toBe('20261106T010000Z/20261106T040000Z')
    expect(url.searchParams.get('location')).toBe('12 Elm St')
    expect(url.searchParams.has('details')).toBe(false)
  })
})
