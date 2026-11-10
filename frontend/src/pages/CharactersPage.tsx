import { Anchor, Button, Group, Modal, Stack, Tabs, Text, Title } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { Link, useNavigate, useSearchParams } from 'react-router'

import {
  type CharacterStatus,
  type RpgSystemSummary,
  STATUS_LABELS,
  useCreateCharacter,
  useMyCharacters,
  useMySystems,
} from '../api/rpg'
import { ErrorNote, LoadingNote, MascotNote } from '../components/mascot/MascotNote'
import { CharacterCard } from '../components/rpg/CharacterCard'
import { CharacterForm } from '../components/rpg/CharacterForm'
import { MySystemAnswers } from '../components/rpg/MySystemAnswers'
import { SystemCard } from '../components/rpg/SystemCard'

/** Opens the new-character form; `groupId` puts them straight into that group's party. */
export function NewCharacterButton({
  system,
  groupId,
  label = 'New character',
}: {
  system?: RpgSystemSummary | null
  groupId?: string
  label?: string
}) {
  const [opened, { open, close }] = useDisclosure(false)
  const create = useCreateCharacter()
  const navigate = useNavigate()
  return (
    <>
      <Button size="xs" onClick={open}>
        {label}
      </Button>
      <Modal opened={opened} onClose={close} title="New character" size="lg">
        <CharacterForm
          initialSystem={system}
          submitLabel="Make character"
          busy={create.isPending}
          error={create.error?.message}
          onCancel={close}
          onSubmit={(fields) =>
            create.mutate(
              { ...fields, group_id: groupId ?? null },
              {
                onSuccess: (made) => {
                  close()
                  if (!groupId) navigate(`/characters/${made.id}`)
                },
              },
            )
          }
        />
      </Modal>
    </>
  )
}

const STATUS_ORDER: CharacterStatus[] = ['active', 'retired', 'dead']

function CharactersTab() {
  const characters = useMyCharacters()
  if (characters.isPending) return <LoadingNote>Loading your characters…</LoadingNote>
  if (characters.isError) {
    return <ErrorNote error={characters.error} onRetry={characters.refetch} />
  }
  if (characters.data.length === 0) {
    return (
      <MascotNote pose="wave" title="No characters yet">
        <Text c="dimmed" maw={420}>
          Make a character for any system, then add them to one of your RPG groups' parties.
        </Text>
      </MascotNote>
    )
  }
  return (
    <Stack>
      {STATUS_ORDER.map((status) => {
        const list = characters.data.filter((c) => c.status === status)
        if (list.length === 0) return null
        return (
          <Stack key={status} gap="xs">
            {status !== 'active' && <Title order={5}>{STATUS_LABELS[status]}</Title>}
            {list.map((c) => (
              <CharacterCard key={c.id} character={c}>
                {c.group && (
                  <Text size="xs" c="dimmed">
                    In {c.group.name}
                  </Text>
                )}
              </CharacterCard>
            ))}
          </Stack>
        )
      })}
    </Stack>
  )
}

function SystemsTab() {
  const systems = useMySystems()
  if (systems.isPending) return <LoadingNote>Loading your systems…</LoadingNote>
  if (systems.isError) return <ErrorNote error={systems.error} onRetry={systems.refetch} />
  if (systems.data.length === 0) {
    return (
      <MascotNote pose="think" title="No systems yet">
        <Text c="dimmed" maw={420}>
          <Anchor component={Link} to="/rpg-systems">
            Search for a system
          </Anchor>{' '}
          to say you know it, can GM it, or want to play it.
        </Text>
      </MascotNote>
    )
  }
  return (
    <Stack gap="xs">
      {systems.data.map((row) => (
        <SystemCard
          key={row.system.id}
          system={row.system}
          below={<MySystemAnswers systemId={row.system.id} row={row} />}
        />
      ))}
      <Anchor component={Link} to="/rpg-systems" size="sm">
        Find another system
      </Anchor>
    </Stack>
  )
}

/** Your characters and the systems you know, on two tabs (`?tab=systems`). */
export function CharactersPage() {
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') === 'systems' ? 'systems' : 'characters'
  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>My RPGs</Title>
        <NewCharacterButton />
      </Group>
      <Tabs
        value={tab}
        onChange={(value) => setParams(value === 'systems' ? { tab: 'systems' } : {})}
      >
        <Tabs.List>
          <Tabs.Tab value="characters">Characters</Tabs.Tab>
          <Tabs.Tab value="systems">Systems</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="characters" pt="md">
          <CharactersTab />
        </Tabs.Panel>
        <Tabs.Panel value="systems" pt="md">
          <SystemsTab />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  )
}
