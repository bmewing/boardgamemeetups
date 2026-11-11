import { Anchor, Modal, Stack, Text } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { useNavigate } from 'react-router'

import { useAddCustomGame } from '../api/games'
import { CustomGameForm } from './CustomGameForm'

/** For a game BGG doesn't list: one you designed, or that just isn't there. */
export function AddCustomGame({ name }: { name: string }) {
  const [opened, { open, close }] = useDisclosure(false)
  const add = useAddCustomGame()
  const navigate = useNavigate()
  return (
    <>
      <Text size="sm" c="dimmed">
        Not on BoardGameGeek? Something you designed, or a game BGG just doesn't list?{' '}
        <Anchor component="button" type="button" size="sm" onClick={open}>
          Add it yourself
        </Anchor>
      </Text>
      <Modal opened={opened} onClose={close} title="Add a game that isn't on BGG">
        <Stack>
          <Text size="sm" c="dimmed">
            It goes in your games as one you own. It won't come up in anyone else's search or
            imports, but friends who see it in your games can add it to theirs.
          </Text>
          <CustomGameForm
            initial={{ name }}
            submitLabel="Add game"
            busy={add.isPending}
            error={add.error?.message}
            onCancel={close}
            onSubmit={(game) =>
              add.mutate(game, { onSuccess: (added) => navigate(`/games/${added.id}`) })
            }
          />
        </Stack>
      </Modal>
    </>
  )
}
