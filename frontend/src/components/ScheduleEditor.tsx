import { NumberInput, SegmentedControl, Select, Stack, Text, TextInput } from '@mantine/core'

import type { Schedule } from '../api/groups'
import { ordinal, todayIso, WEEKDAY_NAMES } from './meetupFormat'

type Kind = 'none' | Schedule['kind']

const WEEKDAY_OPTIONS = WEEKDAY_NAMES.map((name, i) => ({ value: String(i), label: name }))
const NTH_OPTIONS = [
  { value: '1', label: 'First' },
  { value: '2', label: 'Second' },
  { value: '3', label: 'Third' },
  { value: '4', label: 'Fourth' },
  { value: '-1', label: 'Last' },
]
const DAY_OPTIONS = Array.from({ length: 31 }, (_, i) => ({
  value: String(i + 1),
  label: ordinal(i + 1),
}))

/** Monday is 0, as the API counts. */
const weekdayOf = (isoDate: string) => (new Date(`${isoDate}T12:00:00`).getDay() + 6) % 7

function blank(kind: Kind, from: Schedule | null): Schedule | null {
  const starts_on = from?.starts_on ?? todayIso()
  const weekday = from && 'weekday' in from ? from.weekday : weekdayOf(starts_on)
  switch (kind) {
    case 'none':
      return null
    case 'weekly':
      return { kind, every_weeks: 1, weekday, starts_on }
    case 'monthly_weekday':
      return { kind, nth: 1, weekday, starts_on }
    case 'monthly_day':
      return { kind, day: Number(starts_on.slice(8, 10)), starts_on }
  }
}

/** Pick how often the group meets: every N weeks, the Nth weekday, or day X of the month. */
export function ScheduleEditor({
  value,
  onChange,
}: {
  value: Schedule | null
  onChange: (schedule: Schedule | null) => void
}) {
  const kind: Kind = value?.kind ?? 'none'

  return (
    <Stack gap="sm">
      <SegmentedControl
        value={kind}
        onChange={(k) => onChange(blank(k as Kind, value))}
        data={[
          { value: 'none', label: 'No schedule' },
          { value: 'weekly', label: 'Weekly' },
          { value: 'monthly_weekday', label: 'Monthly by weekday' },
          { value: 'monthly_day', label: 'Monthly by date' },
        ]}
        fullWidth
      />
      {value === null && (
        <Text size="sm" c="dimmed">
          Add dates one at a time from the Dates tab.
        </Text>
      )}
      {value?.kind === 'weekly' && (
        <>
          <NumberInput
            label="Every how many weeks"
            min={1}
            max={12}
            value={value.every_weeks ?? 1}
            onChange={(v) => onChange({ ...value, every_weeks: typeof v === 'number' ? v : 1 })}
          />
          <Select
            label="On"
            data={WEEKDAY_OPTIONS}
            allowDeselect={false}
            value={String(value.weekday)}
            onChange={(v) => onChange({ ...value, weekday: Number(v) })}
          />
        </>
      )}
      {value?.kind === 'monthly_weekday' && (
        <>
          <Select
            label="Which one"
            data={NTH_OPTIONS}
            allowDeselect={false}
            value={String(value.nth)}
            onChange={(v) => onChange({ ...value, nth: Number(v) as typeof value.nth })}
          />
          <Select
            label="Day"
            data={WEEKDAY_OPTIONS}
            allowDeselect={false}
            value={String(value.weekday)}
            onChange={(v) => onChange({ ...value, weekday: Number(v) })}
          />
        </>
      )}
      {value?.kind === 'monthly_day' && (
        <Select
          label="Day of the month"
          description="Months without this day are skipped."
          data={DAY_OPTIONS}
          allowDeselect={false}
          value={String(value.day)}
          onChange={(v) => onChange({ ...value, day: Number(v) })}
        />
      )}
      {value && (
        <TextInput
          label="Starting"
          description={
            value.kind === 'weekly' && (value.every_weeks ?? 1) > 1
              ? 'Weeks are counted from here.'
              : undefined
          }
          type="date"
          value={value.starts_on}
          onChange={(e) =>
            e.currentTarget.value && onChange({ ...value, starts_on: e.currentTarget.value })
          }
        />
      )}
    </Stack>
  )
}
