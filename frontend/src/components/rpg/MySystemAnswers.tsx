import { Chip, Group, Stack, Text } from '@mantine/core'

import { type MySystem, type MySystemUpdate, useUpdateMySystem } from '../../api/rpg'

/** One-tap answers about a system: whether you know it, can GM it, or want to play it. */
export function MySystemAnswers({ systemId, row }: { systemId: number; row?: MySystem }) {
  const update = useUpdateMySystem()
  const save = (changes: MySystemUpdate) => update.mutate({ systemId, changes })
  return (
    <Stack gap={4}>
      <Group gap="xs">
        <Chip size="xs" checked={row?.knows ?? false} onChange={(on) => save({ knows: on })}>
          I know it
        </Chip>
        <Chip size="xs" checked={row?.can_gm ?? false} onChange={(on) => save({ can_gm: on })}>
          I can GM it
        </Chip>
        <Chip
          size="xs"
          checked={row?.want_to_play ?? false}
          onChange={(on) => save({ want_to_play: on })}
        >
          Want to play
        </Chip>
      </Group>
      {update.isError && (
        <Text size="xs" c="red">
          {update.error.message}
        </Text>
      )}
    </Stack>
  )
}
