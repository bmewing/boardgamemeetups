import {
  Alert,
  Button,
  Group,
  NumberInput,
  SegmentedControl,
  Stack,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core'
import { type FormEvent, useState } from 'react'

import {
  type Character,
  type CharacterStatus,
  type RpgSystemSummary,
  STATUS_LABELS,
} from '../../api/rpg'
import { RpgSystemSearchSelect } from './RpgSystemSearchSelect'

/** Everything the form edits; the group (party) is chosen elsewhere. */
export interface CharacterFields {
  name: string
  system_id: number
  class_role: string | null
  level: number | null
  ancestry: string | null
  pronouns: string | null
  status: CharacterStatus
  notes: string | null
  portrait_url: string | null
  sheet_url: string | null
}

const WEB_ADDRESS = /^https?:\/\/\S+$/i

/** A character's basic details, for making one or changing it. */
export function CharacterForm({
  initial,
  initialSystem,
  submitLabel,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  initial?: Character
  initialSystem?: RpgSystemSummary | null
  submitLabel: string
  busy: boolean
  error?: string | null
  onSubmit: (character: CharacterFields) => void
  onCancel?: () => void
}) {
  const [system, setSystem] = useState<RpgSystemSummary | null>(
    initial?.system ?? initialSystem ?? null,
  )
  const [text, setText] = useState({
    name: initial?.name ?? '',
    class_role: initial?.class_role ?? '',
    ancestry: initial?.ancestry ?? '',
    pronouns: initial?.pronouns ?? '',
    notes: initial?.notes ?? '',
    portrait_url: initial?.portrait_url ?? '',
    sheet_url: initial?.sheet_url ?? '',
  })
  const [level, setLevel] = useState<number | null>(initial?.level ?? null)
  const [status, setStatus] = useState<CharacterStatus>(initial?.status ?? 'active')
  const [problem, setProblem] = useState<string | null>(null)

  const field = (key: keyof typeof text, label: string, maxLength: number, extra = {}) => (
    <TextInput
      label={label}
      maxLength={maxLength}
      value={text[key]}
      onChange={(e) => {
        const value = e.currentTarget.value
        setText((t) => ({ ...t, [key]: value }))
      }}
      {...extra}
    />
  )

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const trimmed = Object.fromEntries(
      Object.entries(text).map(([k, v]) => [k, v.trim()]),
    ) as typeof text
    if (!trimmed.name) return setProblem('Give your character a name')
    if (!system) return setProblem('Pick the system they play in')
    for (const key of ['portrait_url', 'sheet_url'] as const) {
      if (trimmed[key] && !WEB_ADDRESS.test(trimmed[key])) {
        return setProblem('Links need to start with http:// or https://')
      }
    }
    setProblem(null)
    onSubmit({
      name: trimmed.name,
      system_id: system.id,
      class_role: trimmed.class_role || null,
      level,
      ancestry: trimmed.ancestry || null,
      pronouns: trimmed.pronouns || null,
      status,
      notes: trimmed.notes || null,
      portrait_url: trimmed.portrait_url || null,
      sheet_url: trimmed.sheet_url || null,
    })
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {field('name', 'Name', 80, { required: true, 'data-autofocus': true })}
        <RpgSystemSearchSelect label="System" required value={system} onPick={setSystem} />
        <Group grow align="flex-start">
          {field('class_role', 'Class or role', 120, { placeholder: 'e.g. Wizard, Cutter' })}
          <NumberInput
            label="Level"
            allowDecimal={false}
            allowNegative={false}
            min={0}
            max={1000}
            value={level ?? ''}
            onChange={(v) => setLevel(typeof v === 'number' ? v : null)}
          />
        </Group>
        <Group grow align="flex-start">
          {field('ancestry', 'Ancestry', 120, { placeholder: 'e.g. Elf, Skovlander' })}
          {field('pronouns', 'Pronouns', 40)}
        </Group>
        <Stack gap={4}>
          <Text size="sm" fw={500}>
            Status
          </Text>
          <SegmentedControl
            aria-label="Status"
            value={status}
            onChange={(v) => setStatus(v as CharacterStatus)}
            data={Object.entries(STATUS_LABELS).map(([value, label]) => ({ value, label }))}
          />
        </Stack>
        <Textarea
          label="Notes"
          description="Backstory, goals, anything else. Your party can see it."
          autosize
          minRows={3}
          maxLength={10000}
          value={text.notes}
          onChange={(e) => {
            const notes = e.currentTarget.value
            setText((t) => ({ ...t, notes }))
          }}
        />
        {field('portrait_url', 'Portrait (image link)', 1024, { placeholder: 'https://…' })}
        {field('sheet_url', 'Character sheet link', 1024, {
          placeholder: 'D&D Beyond, Demiplane, a shared doc…',
        })}
        {(problem ?? error) && <Alert color="red">{problem ?? error}</Alert>}
        <Group justify="flex-end">
          {onCancel && (
            <Button variant="default" onClick={onCancel}>
              Cancel
            </Button>
          )}
          <Button type="submit" loading={busy}>
            {submitLabel}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
