import { Accordion, Alert, Badge, Button, Card, Checkbox, Group, Stack, Text } from '@mantine/core'
import { useState } from 'react'
import { Link } from 'react-router'

import {
  type ChangeIn,
  type FieldChange,
  type GameDiff,
  type ImportPreview,
  type ImportResult,
  type ImportSource,
  useApplyImport,
} from '../api/collection'
import { FIELD_LABELS, formatValue, plural } from './userGameFields'

const key = (gameId: number, field: string) => `${gameId}:${field}`

/**
 * Everything is kept except clearing games BGG no longer lists and bringing back games the
 * user removed here; those the user opts into.
 */
function defaultSelection(preview: ImportPreview): Set<string> {
  const keys = new Set<string>()
  for (const game of preview.games) {
    if (game.removed_before) continue
    for (const change of game.changes) {
      if (change.kind !== 'not_on_source') keys.add(key(game.game.id, change.field))
    }
  }
  return keys
}

function KindBadge({ kind }: { kind: FieldChange['kind'] }) {
  if (kind === 'overwrite')
    return (
      <Badge size="xs" color="orange" variant="light">
        Overwrites yours
      </Badge>
    )
  if (kind === 'fill')
    return (
      <Badge size="xs" variant="light">
        Fills a blank
      </Badge>
    )
  return (
    <Badge size="xs" color="gray" variant="light">
      Clears
    </Badge>
  )
}

interface SectionProps {
  games: GameDiff[]
  selected: Set<string>
  onToggle: (keys: string[], on: boolean) => void
  /** New games are kept or skipped whole; existing games change field by field. */
  wholeGames?: boolean
}

function ChangeList({ games, selected, onToggle, wholeGames = false }: SectionProps) {
  return (
    <Stack gap="xs">
      {games.map((game) => {
        const keys = game.changes.map((c) => key(game.game.id, c.field))
        const kept = keys.filter((k) => selected.has(k)).length
        const name = (
          <Text fw={600} size="sm">
            {game.game.name}
            {game.game.year_published && (
              <Text span c="dimmed" fw={400} inherit>
                {' '}
                ({game.game.year_published})
              </Text>
            )}
          </Text>
        )
        if (wholeGames) {
          return (
            <Checkbox
              key={game.game.id}
              checked={kept === keys.length}
              indeterminate={kept > 0 && kept < keys.length}
              onChange={(e) => onToggle(keys, e.currentTarget.checked)}
              label={name}
              description={game.changes
                .map((c) => `${FIELD_LABELS[c.field]}: ${formatValue(c.field, c.incoming)}`)
                .join(' · ')}
            />
          )
        }
        return (
          <Card key={game.game.id} withBorder padding="xs">
            <Stack gap={6}>
              {name}
              {game.changes.map((change) => {
                const k = key(game.game.id, change.field)
                return (
                  <Checkbox
                    key={k}
                    checked={selected.has(k)}
                    onChange={(e) => onToggle([k], e.currentTarget.checked)}
                    label={
                      <Group gap="xs">
                        <Text size="sm">
                          {FIELD_LABELS[change.field]}: {formatValue(change.field, change.current)}{' '}
                          → <b>{formatValue(change.field, change.incoming)}</b>
                        </Text>
                        <KindBadge kind={change.kind} />
                      </Group>
                    }
                  />
                )
              })}
            </Stack>
          </Card>
        )
      })}
    </Stack>
  )
}

function SectionToggle({ games, selected, onToggle }: SectionProps) {
  const keys = games.flatMap((g) => g.changes.map((c) => key(g.game.id, c.field)))
  const kept = keys.filter((k) => selected.has(k)).length
  return (
    <Checkbox
      size="xs"
      label="Keep all"
      checked={kept === keys.length}
      indeterminate={kept > 0 && kept < keys.length}
      onChange={(e) => onToggle(keys, e.currentTarget.checked)}
    />
  )
}

// How the summary names where the games came from.
const WORDS: Record<ImportSource, { Place: string; on: string; Doing: string }> = {
  bgg: { Place: 'BGG', on: 'on BGG', Doing: 'Pulling' },
  file: { Place: 'The file', on: 'in the file', Doing: 'Importing' },
}

/** Every change an import would make, to keep or skip one by one, and the apply button. */
export function PreviewView({
  preview,
  source,
  onApplied,
}: {
  preview: ImportPreview
  source: ImportSource
  onApplied: (result: ImportResult) => void
}) {
  const apply = useApplyImport()
  const [selected, setSelected] = useState(() => defaultSelection(preview))
  const toggle = (keys: string[], on: boolean) =>
    setSelected((current) => {
      const next = new Set(current)
      for (const k of keys) {
        if (on) next.add(k)
        else next.delete(k)
      }
      return next
    })

  const newGames = preview.games.filter((g) => g.is_new && !g.removed_before)
  const removedBefore = preview.games.filter((g) => g.removed_before)
  const updated = preview.games.filter((g) => !g.is_new && g.on_source)
  const gone = preview.games.filter((g) => !g.on_source)
  const kept: ChangeIn[] = preview.games.flatMap((g) =>
    g.changes
      .filter((c) => selected.has(key(g.game.id, c.field)))
      .map((c) => ({
        game_id: g.game.id,
        field: c.field,
        expected: c.current,
        value: c.incoming,
      })),
  )
  const keptOverwrites = preview.games.reduce(
    (n, g) =>
      n +
      g.changes.filter((c) => c.kind === 'overwrite' && selected.has(key(g.game.id, c.field)))
        .length,
    0,
  )
  const { counts } = preview
  const words = WORDS[source]
  const additions = [
    counts.new_games > 0 && `add ${plural(counts.new_games, 'new game')}`,
    counts.fills > 0 && `fill ${plural(counts.fills, 'blank')}`,
  ].filter((part) => part !== false)

  if (preview.games.length === 0) {
    return (
      <Stack align="flex-start">
        <Alert color="meeple" title="Already up to date" w="100%">
          {words.Place} lists {plural(counts.games_on_source, 'game')}, and nothing there differs
          from what you have here.
        </Alert>
        <Button component={Link} to="/collection">
          Go to my games
        </Button>
      </Stack>
    )
  }

  const sections = [
    newGames.length > 0 && {
      value: 'new',
      title: `New games (${newGames.length})`,
      games: newGames,
      whole: true,
    },
    removedBefore.length > 0 && {
      value: 'removed',
      title: `Removed here before (${removedBefore.length})`,
      games: removedBefore,
      whole: true,
    },
    updated.length > 0 && {
      value: 'updated',
      title: `Changes to games you have (${updated.length})`,
      games: updated,
      whole: false,
    },
    gone.length > 0 && {
      value: 'gone',
      title: `Not ${words.on} any more (${gone.length})`,
      games: gone,
      whole: false,
    },
  ].filter((s) => s !== false)

  return (
    <Stack>
      <Text>
        {words.Place} lists {plural(counts.games_on_source, 'game')}.
        {additions.length > 0 && ` ${words.Doing} would ${additions.join(' and ')}.`}
      </Text>
      {counts.overwrites > 0 ? (
        <Text fw={700} c="orange">
          It would overwrite {plural(counts.overwrites, 'answer')} you gave here.
        </Text>
      ) : (
        <Text>None of your answers here would be overwritten.</Text>
      )}
      {counts.not_on_source > 0 && (
        <Text size="sm" c="dimmed">
          {counts.not_on_source === 1
            ? `1 game you have here isn't ${words.on}; it's left alone unless you tick it.`
            : `${counts.not_on_source} games you have here aren't ${words.on}; they're left alone unless you tick them.`}
        </Text>
      )}
      {counts.removed_before > 0 && (
        <Text size="sm" c="dimmed">
          {counts.removed_before === 1
            ? `1 game you removed here is still ${words.on}; it's left out unless you tick it.`
            : `${counts.removed_before} games you removed here are still ${words.on}; they're left out unless you tick them.`}
        </Text>
      )}
      <Accordion
        multiple
        variant="separated"
        defaultValue={sections
          .filter((s) => s.value !== 'removed' && (!s.whole || s.games.length <= 20))
          .map((s) => s.value)}
      >
        {sections.map((s) => (
          <Accordion.Item key={s.value} value={s.value}>
            <Accordion.Control>{s.title}</Accordion.Control>
            <Accordion.Panel>
              <Stack>
                <SectionToggle games={s.games} selected={selected} onToggle={toggle} />
                <ChangeList
                  games={s.games}
                  selected={selected}
                  onToggle={toggle}
                  wholeGames={s.whole}
                />
              </Stack>
            </Accordion.Panel>
          </Accordion.Item>
        ))}
      </Accordion>
      {apply.isError && <Alert color="red">{apply.error.message}</Alert>}
      <Group>
        <Button
          color={keptOverwrites ? 'orange' : undefined}
          disabled={kept.length === 0}
          loading={apply.isPending}
          onClick={() => apply.mutate({ changes: kept, source }, { onSuccess: onApplied })}
        >
          Apply {plural(kept.length, 'change')}
          {keptOverwrites > 0 && ` (${keptOverwrites} overwrite yours)`}
        </Button>
        <Button component={Link} to="/collection" variant="default">
          Cancel
        </Button>
      </Group>
    </Stack>
  )
}

export function ResultView({
  result,
  onAgain,
  againLabel,
}: {
  result: ImportResult
  onAgain: () => void
  againLabel: string
}) {
  return (
    <Stack>
      <Alert color="meeple" title="Saved">
        Applied {plural(result.applied, 'change')}.
      </Alert>
      {result.skipped.length > 0 && (
        <Alert color="yellow" title={`Skipped ${plural(result.skipped.length, 'change')}`}>
          These games changed after the preview was made, so their new values were kept. Pull again
          to see what still differs.
        </Alert>
      )}
      <Group>
        <Button component={Link} to="/collection">
          Go to my games
        </Button>
        <Button variant="default" onClick={onAgain}>
          {againLabel}
        </Button>
      </Group>
    </Stack>
  )
}
