import { Alert, Button, Group, NumberInput, Stack, Textarea, TextInput } from '@mantine/core'
import { type FormEvent, useState } from 'react'

export interface MeetupFields {
  local_date: string
  local_time: string // "19:00"
  duration_minutes: number
  location: string
  notes: string
}

/** Date, time, length, place and notes for one meetup, as typed by the person running it. */
export function MeetupForm({
  initial,
  submitLabel,
  busy,
  error,
  onSubmit,
}: {
  initial: MeetupFields
  submitLabel: string
  busy: boolean
  error?: string | null
  onSubmit: (fields: MeetupFields) => void
}) {
  const [fields, setFields] = useState(initial)
  const set = <K extends keyof MeetupFields>(key: K, value: MeetupFields[K]) =>
    setFields((f) => ({ ...f, [key]: value }))

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (fields.local_date && fields.local_time) onSubmit(fields)
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        <Group grow>
          <TextInput
            label="Date"
            type="date"
            required
            value={fields.local_date}
            onChange={(e) => set('local_date', e.currentTarget.value)}
          />
          <TextInput
            label="Start"
            type="time"
            required
            value={fields.local_time}
            onChange={(e) => set('local_time', e.currentTarget.value)}
          />
        </Group>
        <NumberInput
          label="Length (minutes)"
          min={15}
          max={1440}
          step={30}
          value={fields.duration_minutes}
          onChange={(v) => set('duration_minutes', typeof v === 'number' ? v : 180)}
        />
        <TextInput
          label="Place"
          maxLength={200}
          value={fields.location}
          onChange={(e) => set('location', e.currentTarget.value)}
        />
        <Textarea
          label="Notes"
          autosize
          minRows={2}
          maxLength={2000}
          value={fields.notes}
          onChange={(e) => set('notes', e.currentTarget.value)}
        />
        {error && <Alert color="red">{error}</Alert>}
        <Group justify="flex-end">
          <Button type="submit" loading={busy}>
            {submitLabel}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
