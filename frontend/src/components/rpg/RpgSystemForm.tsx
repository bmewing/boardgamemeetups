import { Alert, Button, Group, Stack, Textarea, TextInput } from '@mantine/core'
import { type FormEvent, useState } from 'react'

import type { CustomSystemIn } from '../../api/rpg'

/** A system that isn't on RPGGeek: a homebrew, or one RPGGeek just doesn't list. */
export function RpgSystemForm({
  initial,
  submitLabel,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  initial?: Partial<CustomSystemIn>
  submitLabel: string
  busy: boolean
  error?: string | null
  onSubmit: (system: CustomSystemIn) => void
  onCancel?: () => void
}) {
  const [name, setName] = useState(initial?.name ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [problem, setProblem] = useState<string | null>(null)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return setProblem('Give the system a name')
    setProblem(null)
    onSubmit({ name: name.trim(), description: description.trim() || null })
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        <TextInput
          label="Name"
          required
          maxLength={200}
          data-autofocus
          value={name}
          onChange={(e) => setName(e.currentTarget.value)}
        />
        <Textarea
          label="Description"
          autosize
          minRows={3}
          maxLength={5000}
          value={description}
          onChange={(e) => setDescription(e.currentTarget.value)}
        />
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
