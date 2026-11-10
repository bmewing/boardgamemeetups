import {
  Anchor,
  Badge,
  Button,
  Card,
  Group,
  Image,
  Modal,
  SimpleGrid,
  Spoiler,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { useParams } from 'react-router'

import { useMe } from '../api/me'
import {
  type RpgSystemDetail,
  useMyCharacters,
  useMySystems,
  useRpgSystem,
  useUpdateCustomSystem,
} from '../api/rpg'
import { ErrorNote, LoadingNote } from '../components/mascot/MascotNote'
import { CharacterCard } from '../components/rpg/CharacterCard'
import { MySystemAnswers } from '../components/rpg/MySystemAnswers'
import { RpgSystemForm } from '../components/rpg/RpgSystemForm'
import { NewCharacterButton } from './CharactersPage'

/** Whoever added a system that isn't on RPGGeek can fix its details. */
function EditCustomSystem({ system }: { system: RpgSystemDetail }) {
  const [opened, { open, close }] = useDisclosure(false)
  const update = useUpdateCustomSystem(system.id)
  return (
    <>
      <Button size="xs" variant="default" w="fit-content" onClick={open}>
        Edit details
      </Button>
      <Modal opened={opened} onClose={close} title={`Edit ${system.name}`}>
        <RpgSystemForm
          initial={system}
          submitLabel="Save"
          busy={update.isPending}
          error={update.error?.message}
          onCancel={close}
          onSubmit={(changes) => update.mutate(changes, { onSuccess: close })}
        />
      </Modal>
    </>
  )
}

export function RpgSystemPage() {
  const systemId = Number(useParams().systemId)
  const system = useRpgSystem(systemId)
  const me = useMe()
  const mySystems = useMySystems()
  const characters = useMyCharacters()

  if (system.isPending) return <LoadingNote>Loading the system…</LoadingNote>
  if (system.isError) return <ErrorNote error={system.error} onRetry={system.refetch} />

  const s = system.data
  const row = mySystems.data?.find((m) => m.system.id === s.id)
  const mine = (characters.data ?? []).filter((c) => c.system.id === s.id)

  return (
    <Stack>
      <SimpleGrid cols={{ base: 1, sm: s.image_url ? 2 : 1 }}>
        {s.image_url && (
          <Image src={s.image_url} alt={s.name} radius="md" mah={360} fit="contain" />
        )}
        <Stack gap="xs">
          <Title order={2}>{s.name}</Title>
          {s.description && (
            <Spoiler maxHeight={160} showLabel="Read more" hideLabel="Show less">
              <Text size="sm" style={{ whiteSpace: 'pre-line' }}>
                {s.description}
              </Text>
            </Spoiler>
          )}
          {s.rpggeek_url ? (
            <Anchor href={s.rpggeek_url} target="_blank" size="sm">
              View on RPGGeek
            </Anchor>
          ) : (
            <Group gap="xs">
              <Badge variant="light" color="olive">
                Not on RPGGeek
              </Badge>
              <Text size="sm" c="dimmed">
                Added by someone here.
              </Text>
            </Group>
          )}
          {s.is_custom && me.data && s.created_by_id === me.data.id && (
            <EditCustomSystem system={s} />
          )}
        </Stack>
      </SimpleGrid>
      <Card withBorder>
        <Stack gap="xs">
          <Title order={4}>You and {s.name}</Title>
          <MySystemAnswers systemId={s.id} row={row} />
        </Stack>
      </Card>
      <Group justify="space-between">
        <Title order={4}>Your characters</Title>
        <NewCharacterButton system={s} />
      </Group>
      {mine.length === 0 ? (
        <Text c="dimmed" size="sm">
          None yet in {s.name}.
        </Text>
      ) : (
        <Stack gap="xs">
          {mine.map((c) => (
            <CharacterCard key={c.id} character={c} showSystem={false} />
          ))}
        </Stack>
      )}
    </Stack>
  )
}
