import { Alert, Button, Card, Group, Stack, Text, Textarea, Title } from '@mantine/core'
import { useState } from 'react'

import { type Meetup, useSaveRecap } from '../../api/groups'

function RecapEditor({ meetup, onDone }: { meetup: Meetup; onDone: () => void }) {
  const save = useSaveRecap(meetup.id)
  const [text, setText] = useState(meetup.recap ?? '')
  return (
    <Stack gap="xs">
      <Textarea
        aria-label="Session recap"
        placeholder="What happened? Who did what, where you left off, loot, loose ends…"
        autosize
        minRows={4}
        maxLength={10000}
        value={text}
        onChange={(e) => setText(e.currentTarget.value)}
        autoFocus
      />
      {save.isError && <Alert color="red">{save.error.message}</Alert>}
      <Group justify="flex-end" gap="xs">
        <Button variant="default" size="xs" onClick={onDone}>
          Cancel
        </Button>
        <Button
          size="xs"
          loading={save.isPending}
          onClick={() => save.mutate(text, { onSuccess: onDone })}
        >
          Save recap
        </Button>
      </Group>
    </Stack>
  )
}

/**
 * RPG dates: once a session has started, anyone in the group can write what happened;
 * before it, the last session's recap is a reminder of where things stand.
 */
export function RecapPanel({ meetup }: { meetup: Meetup }) {
  const [editing, setEditing] = useState(false)
  const [now] = useState(() => Date.now())
  if (meetup.status === 'cancelled') return null
  const started = new Date(meetup.starts_at).getTime() <= now

  if (!started) {
    if (!meetup.previous_recap) return null
    return (
      <Card withBorder padding="md">
        <Stack gap="xs">
          <Title order={4}>Last session</Title>
          <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
            {meetup.previous_recap}
          </Text>
        </Stack>
      </Card>
    )
  }

  return (
    <Card withBorder padding="md">
      <Stack gap="xs">
        <Group justify="space-between">
          <Title order={4}>Session recap</Title>
          {!editing && (
            <Button size="xs" variant="default" onClick={() => setEditing(true)}>
              {meetup.recap ? 'Edit' : 'Write the recap'}
            </Button>
          )}
        </Group>
        {editing ? (
          <RecapEditor meetup={meetup} onDone={() => setEditing(false)} />
        ) : meetup.recap ? (
          <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
            {meetup.recap}
          </Text>
        ) : (
          <Text size="sm" c="dimmed">
            Nobody has written up this session yet. Anyone in the group can.
          </Text>
        )}
      </Stack>
    </Card>
  )
}
