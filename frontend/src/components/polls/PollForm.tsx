import { Button, Chip, Group, Select, Stack, Text, TextInput } from '@mantine/core'
import { useMemo, useState } from 'react'

import type { PollCreate } from '../../api/polls'
import { isoDate } from '../meetupFormat'
import { addDays, datesBetween, halfHours, timeLabel } from './pollFormat'

const MAX_DAYS = 62
const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const DURATIONS = [
  { value: '60', label: '1 hour' },
  { value: '90', label: '1½ hours' },
  { value: '120', label: '2 hours' },
  { value: '150', label: '2½ hours' },
  { value: '180', label: '3 hours' },
  { value: '240', label: '4 hours' },
]
const browserTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone

/** Start a find-a-time poll: which days, which hours, and how long the thing takes. */
export function PollForm({
  defaultTitle,
  timeZone = browserTimeZone,
  busy,
  error,
  onSubmit,
}: {
  defaultTitle: string
  timeZone?: string
  busy: boolean
  error: string | null
  onSubmit: (poll: PollCreate) => void
}) {
  const [title, setTitle] = useState(defaultTitle)
  const [from, setFrom] = useState(() => isoDate(addDays(new Date(), 1)))
  const [to, setTo] = useState(() => isoDate(addDays(new Date(), 14)))
  const [weekdays, setWeekdays] = useState(['0', '1', '2', '3', '4', '5', '6'])
  const [start, setStart] = useState('18:00')
  const [end, setEnd] = useState('21:00')
  const [duration, setDuration] = useState('120')

  const times = useMemo(() => halfHours(), [])
  const startOptions = times.map((t) => ({ value: t, label: timeLabel(t) }))
  // Until runs to the end of the day: "24:00" is midnight, sent as 00:00.
  const endOptions = [...times.slice(1), '24:00'].map((t) => ({
    value: t,
    label: t === '24:00' ? 'Midnight' : timeLabel(t),
  }))

  const dates = datesBetween(from, to, weekdays.map(Number))
  const perDay = Math.max(0, times.indexOf(end === '24:00' ? '00:00' : end) - times.indexOf(start))
  const slotsPerDay = end === '24:00' ? 48 - times.indexOf(start) : perDay
  const problem =
    dates.length === 0
      ? 'Pick at least one day.'
      : dates.length > MAX_DAYS
        ? `Pick at most ${MAX_DAYS} days.`
        : slotsPerDay <= 0
          ? 'The window has to end after it starts.'
          : !title.trim()
            ? 'Give the poll a name.'
            : null

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (problem) return
        onSubmit({
          title: title.trim(),
          dates,
          start_time: start,
          end_time: end === '24:00' ? '00:00' : end,
          time_zone: timeZone,
          duration_minutes: Number(duration),
        })
      }}
    >
      <Stack>
        <TextInput
          label="What are you planning?"
          value={title}
          maxLength={120}
          onChange={(e) => setTitle(e.currentTarget.value)}
        />
        <Group grow align="flex-start">
          <TextInput
            type="date"
            label="From"
            value={from}
            onChange={(e) => setFrom(e.currentTarget.value)}
          />
          <TextInput
            type="date"
            label="To"
            value={to}
            min={from}
            onChange={(e) => setTo(e.currentTarget.value)}
          />
        </Group>
        <Chip.Group multiple value={weekdays} onChange={setWeekdays}>
          <Group gap={6}>
            {WEEKDAYS.map((name, i) => (
              <Chip key={name} value={String(i)} size="xs">
                {name}
              </Chip>
            ))}
          </Group>
        </Chip.Group>
        <Group grow>
          <Select
            label="Starting"
            data={startOptions}
            value={start}
            allowDeselect={false}
            onChange={(v) => v && setStart(v)}
          />
          <Select
            label="Until"
            data={endOptions}
            value={end}
            allowDeselect={false}
            onChange={(v) => v && setEnd(v)}
          />
        </Group>
        <Select
          label="It takes about"
          description="The best times are ones that fit the whole thing."
          data={DURATIONS}
          value={duration}
          allowDeselect={false}
          onChange={(v) => v && setDuration(v)}
        />
        {problem ? (
          <Text size="sm" c="red">
            {problem}
          </Text>
        ) : (
          <Text size="sm" c="dimmed">
            {dates.length} {dates.length === 1 ? 'day' : 'days'}, {slotsPerDay}{' '}
            {slotsPerDay === 1 ? 'time' : 'times'} each. Times are in {timeZone.replace(/_/g, ' ')}.
          </Text>
        )}
        {error && (
          <Text size="sm" c="red">
            {error}
          </Text>
        )}
        <Button type="submit" loading={busy} disabled={problem !== null}>
          Ask the group
        </Button>
        <Text size="xs" c="dimmed">
          Everyone in the group gets an email asking when they&apos;re free.
        </Text>
      </Stack>
    </form>
  )
}
