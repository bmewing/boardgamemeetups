import { Anchor, Badge, Group, Select, Stack, Text, Title } from '@mantine/core'
import { Link } from 'react-router'

import { type Group as GroupData, runsGroup } from '../../api/groups'
import {
  type Character,
  type SystemAnswers,
  useMoveCharacter,
  useMyCharacters,
  useParty,
} from '../../api/rpg'
import { NewCharacterButton } from '../../pages/CharactersPage'
import { ErrorNote, LoadingNote, MascotNote } from '../mascot/MascotNote'
import { PersonRow } from '../PersonRow'
import { CharacterCard } from './CharacterCard'

/** Put one of your characters into this group's party, from no party or another one. */
function AddExisting({ groupId, characters }: { groupId: string; characters: Character[] }) {
  const move = useMoveCharacter()
  if (characters.length === 0) return null
  return (
    <Stack gap={4}>
      <Select
        aria-label="Add one of your characters"
        placeholder="Add one of your characters…"
        data={characters.map((c) => ({
          value: c.id,
          label: c.group ? `${c.name} (now in ${c.group.name})` : c.name,
        }))}
        value={null}
        disabled={move.isPending}
        onChange={(id) => {
          const character = characters.find((c) => c.id === id)
          if (character) move.mutate({ character, groupId })
        }}
        w={{ base: '100%', sm: 320 }}
        size="xs"
      />
      {move.isError && (
        <Text size="xs" c="red">
          {move.error.message}
        </Text>
      )}
    </Stack>
  )
}

function answerBadges(answers: SystemAnswers | null) {
  if (!answers) return null
  const badges = [
    answers.can_gm ? 'Can GM it' : answers.knows ? 'Knows it' : null,
    answers.want_to_play ? 'Wants to play' : null,
  ].filter((b): b is string => b !== null)
  return badges.map((b) => (
    <Badge key={b} size="xs" variant="light" color="gray">
      {b}
    </Badge>
  ))
}

/** An RPG group's party: its system, members' characters, and who knows the system. */
export function PartyTab({ group }: { group: GroupData }) {
  const party = useParty(group.id)
  const mine = useMyCharacters()

  if (party.isPending) return <LoadingNote>Gathering the party…</LoadingNote>
  if (party.isError) return <ErrorNote error={party.error} onRetry={party.refetch} />

  const { system, characters, members } = party.data
  const inParty = new Set(characters.map((c) => c.id))
  // Active characters not here yet, in the group's system when it has one.
  const addable = (mine.data ?? []).filter(
    (c) => !inParty.has(c.id) && c.status === 'active' && (!system || c.system.id === system.id),
  )

  return (
    <Stack>
      {system ? (
        <Text>
          Playing{' '}
          <Anchor component={Link} to={`/rpg-systems/${system.id}`} fw={600}>
            {system.name}
          </Anchor>
        </Text>
      ) : (
        <Text c="dimmed">
          No system picked yet.{runsGroup(group.my_role) && ' Pick one in Settings.'}
        </Text>
      )}

      <Group justify="space-between">
        <Title order={4}>Characters</Title>
        <NewCharacterButton system={system} groupId={group.id} />
      </Group>
      <AddExisting groupId={group.id} characters={addable} />
      {characters.length === 0 ? (
        <MascotNote pose="wave" size={96}>
          <Text c="dimmed" size="sm">
            Nobody has added a character yet.
          </Text>
        </MascotNote>
      ) : (
        <Stack gap="xs">
          {characters.map((c) => (
            <CharacterCard key={c.id} character={c} showOwner showSystem={!system} />
          ))}
        </Stack>
      )}

      {system && (
        <Stack gap="xs">
          <Title order={4}>Who knows {system.name}</Title>
          {members.map((m) => (
            <PersonRow
              key={m.person.id}
              person={m.person}
              note={m.is_gm ? 'GM' : m.answers ? undefined : "Hasn't said"}
            >
              <Group gap={4}>{answerBadges(m.answers)}</Group>
            </PersonRow>
          ))}
        </Stack>
      )}
    </Stack>
  )
}
