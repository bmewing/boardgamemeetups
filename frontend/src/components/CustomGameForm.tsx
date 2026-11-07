import { Alert, Button, Group, NumberInput, Stack, TextInput } from '@mantine/core'
import { type FormEvent, useState } from 'react'

import type { CustomGameIn } from '../api/games'

type NumberField = Exclude<keyof CustomGameIn, 'name'>

const blank: CustomGameIn = {
  name: '',
  year_published: null,
  min_players: null,
  max_players: null,
  min_playtime: null,
  max_playtime: null,
  min_age: null,
}

/** The facts about a game that isn't on BGG, as whoever added it tells them. */
export function CustomGameForm({
  initial,
  submitLabel,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  initial?: Partial<CustomGameIn>
  submitLabel: string
  busy: boolean
  error?: string | null
  onSubmit: (game: CustomGameIn) => void
  onCancel?: () => void
}) {
  const [game, setGame] = useState<CustomGameIn>({ ...blank, ...initial })
  const [problem, setProblem] = useState<string | null>(null)

  const number = (field: NumberField, label: string, extra: { min: number; max: number }) => (
    <NumberInput
      label={label}
      allowDecimal={false}
      allowNegative={false}
      {...extra}
      value={game[field] ?? ''}
      onChange={(v) => setGame((g) => ({ ...g, [field]: typeof v === 'number' ? v : null }))}
    />
  )

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const { min_players: fewest, max_players: most, min_playtime: shortest } = game
    if (!game.name.trim()) return setProblem('Give the game a name')
    if (fewest && most && fewest > most) return setProblem("The most players can't be fewer")
    if (shortest && game.max_playtime && shortest > game.max_playtime) {
      return setProblem("The longest game can't be shorter than the shortest")
    }
    setProblem(null)
    onSubmit({ ...game, name: game.name.trim() })
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        <TextInput
          label="Name"
          required
          maxLength={200}
          data-autofocus
          value={game.name}
          onChange={(e) => {
            const name = e.currentTarget.value
            setGame((g) => ({ ...g, name }))
          }}
        />
        <Group grow align="flex-start">
          {number('min_players', 'Fewest players', { min: 1, max: 100 })}
          {number('max_players', 'Most players', { min: 1, max: 100 })}
        </Group>
        <Group grow align="flex-start">
          {number('min_playtime', 'Shortest (minutes)', { min: 1, max: 10080 })}
          {number('max_playtime', 'Longest (minutes)', { min: 1, max: 10080 })}
        </Group>
        <Group grow align="flex-start">
          {number('year_published', 'Year', { min: 1, max: 2200 })}
          {number('min_age', 'Ages (and up)', { min: 1, max: 99 })}
        </Group>
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
