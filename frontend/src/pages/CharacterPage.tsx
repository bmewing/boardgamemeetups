import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Group,
  Image,
  Modal,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { Link, useNavigate, useParams } from 'react-router'

import { useGroups } from '../api/groups'
import { useMe } from '../api/me'
import {
  type Character,
  STATUS_LABELS,
  useCharacter,
  useDeleteCharacter,
  useUpdateCharacter,
} from '../api/rpg'
import { ErrorNote, LoadingNote, MascotNote } from '../components/mascot/MascotNote'
import { characterLine } from '../components/rpg/characterLine'
import { CharacterForm } from '../components/rpg/CharacterForm'

/** Which of your RPG groups this character plays in, if any. */
function PartyPicker({ character }: { character: Character }) {
  const groups = useGroups()
  const update = useUpdateCharacter(character.id, character.group?.id)
  const rpgGroups = (groups.data?.groups ?? []).filter((g) => g.kind === 'rpg')
  const options = rpgGroups.map((g) => ({ value: g.id, label: g.name }))
  if (character.group && !options.some((o) => o.value === character.group?.id)) {
    options.push({ value: character.group.id, label: character.group.name })
  }
  return (
    <Stack gap={4}>
      <Select
        label="Party"
        description={
          rpgGroups.length === 0 ? "You're not in any RPG groups yet." : 'One group at a time.'
        }
        placeholder="Not in a party"
        clearable
        data={options}
        value={character.group?.id ?? null}
        onChange={(groupId) => update.mutate({ group_id: groupId })}
        disabled={update.isPending}
        w={{ base: '100%', sm: 320 }}
      />
      {update.isError && (
        <Text size="xs" c="red">
          {update.error.message}
        </Text>
      )}
    </Stack>
  )
}

function EditCharacter({ character }: { character: Character }) {
  const [opened, { open, close }] = useDisclosure(false)
  const update = useUpdateCharacter(character.id, character.group?.id)
  return (
    <>
      <Button size="xs" variant="default" onClick={open}>
        Edit
      </Button>
      <Modal opened={opened} onClose={close} title={`Edit ${character.name}`} size="lg">
        <CharacterForm
          initial={character}
          submitLabel="Save"
          busy={update.isPending}
          error={update.error?.message}
          onCancel={close}
          onSubmit={(fields) => update.mutate(fields, { onSuccess: close })}
        />
      </Modal>
    </>
  )
}

function DeleteCharacter({ character }: { character: Character }) {
  const [opened, { open, close }] = useDisclosure(false)
  const remove = useDeleteCharacter(character.id, character.group?.id)
  const navigate = useNavigate()
  return (
    <>
      <Button size="xs" variant="subtle" color="red" onClick={open}>
        Delete
      </Button>
      <Modal opened={opened} onClose={close} title={`Delete ${character.name}?`}>
        <Stack>
          <Text size="sm">
            This can't be undone. To keep them around without playing them, mark them retired
            instead.
          </Text>
          {remove.isError && <Alert color="red">{remove.error.message}</Alert>}
          <Group justify="flex-end">
            <Button variant="default" onClick={close}>
              Keep
            </Button>
            <Button
              color="red"
              loading={remove.isPending}
              onClick={() => remove.mutate(undefined, { onSuccess: () => navigate('/characters') })}
            >
              Delete
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  )
}

export function CharacterPage() {
  const characterId = useParams().characterId ?? ''
  const character = useCharacter(characterId)
  const me = useMe()

  if (character.isPending) return <LoadingNote>Loading the character…</LoadingNote>
  if (character.isError) return <ErrorNote error={character.error} onRetry={character.refetch} />
  if (character.data === null) {
    return (
      <MascotNote pose="oops" title="Character not found">
        <Text c="dimmed">It's not yours, and not in the party of a group you're in.</Text>
      </MascotNote>
    )
  }

  const c = character.data
  const mine = me.data?.id === c.owner.id
  const line = characterLine(c)

  return (
    <Stack>
      <SimpleGrid cols={{ base: 1, sm: c.portrait_url ? 2 : 1 }}>
        {c.portrait_url && (
          <Image src={c.portrait_url} alt={c.name} radius="md" mah={360} fit="contain" />
        )}
        <Stack gap="xs">
          <Group gap="xs">
            <Title order={2}>{c.name}</Title>
            {c.pronouns && <Text c="dimmed">({c.pronouns})</Text>}
            <Badge variant="light" color={c.status === 'active' ? 'teal' : 'gray'}>
              {STATUS_LABELS[c.status]}
            </Badge>
          </Group>
          {line && <Text>{line}</Text>}
          <Text size="sm" c="dimmed">
            <Anchor component={Link} to={`/rpg-systems/${c.system.id}`} inherit>
              {c.system.name}
            </Anchor>
            {!mine && ` · played by ${c.owner.display_name}`}
            {c.group && (
              <>
                {' · in '}
                <Anchor component={Link} to={`/groups/${c.group.id}`} inherit>
                  {c.group.name}
                </Anchor>
              </>
            )}
          </Text>
          {c.sheet_url && (
            <Anchor href={c.sheet_url} target="_blank" rel="noopener noreferrer" size="sm">
              Character sheet
            </Anchor>
          )}
          {mine && (
            <Group gap="xs">
              <EditCharacter character={c} />
              <DeleteCharacter character={c} />
            </Group>
          )}
        </Stack>
      </SimpleGrid>
      {c.notes && (
        <Card withBorder>
          <Text style={{ whiteSpace: 'pre-line' }}>{c.notes}</Text>
        </Card>
      )}
      {mine && <PartyPicker character={c} />}
    </Stack>
  )
}
