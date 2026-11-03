import {
  Accordion,
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Center,
  Checkbox,
  Group,
  Loader,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { useState } from 'react'
import { Link } from 'react-router'

import {
  type ChangeIn,
  type FieldChange,
  type GameDiff,
  type ImportPreview,
  type ImportResult,
  useApplyImport,
  useBggPullPreview,
} from '../api/collection'
import { useMe } from '../api/me'
import { FIELD_LABELS, formatValue } from '../components/userGameFields'

const key = (gameId: number, field: string) => `${gameId}:${field}`

/** Everything is kept except clearing games BGG no longer lists, which the user opts into. */
function defaultSelection(preview: ImportPreview): Set<string> {
  const keys = new Set<string>()
  for (const game of preview.games) {
    for (const change of game.changes) {
      if (change.kind !== 'not_on_source') keys.add(key(game.game.id, change.field))
    }
  }
  return keys
}

function plural(n: number, one: string, many = `${one}s`) {
  return `${n} ${n === 1 ? one : many}`
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

function PreviewView({
  preview,
  onApplied,
}: {
  preview: ImportPreview
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

  const newGames = preview.games.filter((g) => g.is_new)
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

  if (preview.games.length === 0) {
    return (
      <Alert color="teal" title="Already up to date">
        BGG lists {plural(counts.games_on_source, 'game')}, and nothing there differs from what you
        have here.
      </Alert>
    )
  }

  const sections = [
    newGames.length > 0 && {
      value: 'new',
      title: `New games (${newGames.length})`,
      games: newGames,
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
      title: `Not on BGG any more (${gone.length})`,
      games: gone,
      whole: false,
    },
  ].filter((s) => s !== false)

  return (
    <Stack>
      <Text>
        BGG lists {plural(counts.games_on_source, 'game')}. Pulling would add{' '}
        {plural(counts.new_games, 'new game')}, fill {plural(counts.fills, 'blank')},{' '}
        <Text span fw={counts.overwrites ? 700 : undefined} c={counts.overwrites ? 'orange' : ''}>
          overwrite {plural(counts.overwrites, 'answer')} you gave here
        </Text>
        , and find {plural(counts.not_on_source, 'game')} you have here that BGG doesn't.
      </Text>
      {gone.length > 0 && (
        <Text size="sm" c="dimmed">
          Games no longer on BGG are left alone unless you tick them.
        </Text>
      )}
      <Accordion
        multiple
        variant="separated"
        defaultValue={sections.filter((s) => !s.whole || s.games.length <= 20).map((s) => s.value)}
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
          onClick={() => apply.mutate(kept, { onSuccess: onApplied })}
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

function ResultView({ result, onAgain }: { result: ImportResult; onAgain: () => void }) {
  return (
    <Stack>
      <Alert color="teal" title="Saved">
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
          Pull again
        </Button>
      </Group>
    </Stack>
  )
}

export function BggPullPage() {
  const me = useMe()
  const pull = useBggPullPreview()
  const [result, setResult] = useState<ImportResult | null>(null)
  const start = () => {
    setResult(null)
    pull.mutate()
  }

  let body
  if (me.isPending) {
    body = <Loader />
  } else if (me.isError) {
    body = <Alert color="red">{me.error.message}</Alert>
  } else if (!me.data.bgg_username) {
    body = (
      <Alert title="Add your BGG username first">
        Pulling needs to know whose collection to read.{' '}
        <Anchor component={Link} to="/profile">
          Set it on your profile.
        </Anchor>
      </Alert>
    )
  } else if (result) {
    body = <ResultView result={result} onAgain={start} />
  } else if (pull.isPending) {
    body = (
      <Center py="xl">
        <Stack align="center" gap="xs">
          <Loader />
          <Text c="dimmed" size="sm">
            Asking BoardGameGeek… big collections can take up to a minute.
          </Text>
        </Stack>
      </Center>
    )
  } else if (pull.isSuccess) {
    body = <PreviewView key={pull.submittedAt} preview={pull.data} onApplied={setResult} />
  } else {
    const last = me.data.bgg_pulled_at
    body = (
      <Stack align="flex-start">
        <Text>
          This reads the BGG collection for <b>{me.data.bgg_username}</b> and shows every change
          before anything is saved. Nothing is ever sent back to BGG.
        </Text>
        {last && (
          <Text size="sm" c="dimmed">
            Last pulled {new Date(last).toLocaleString()}.
          </Text>
        )}
        {pull.isError && <Alert color="red">{pull.error.message}</Alert>}
        <Button onClick={start}>{pull.isError ? 'Try again' : 'Fetch from BGG'}</Button>
      </Stack>
    )
  }

  return (
    <Stack>
      <Title order={2}>Pull from BoardGameGeek</Title>
      {body}
    </Stack>
  )
}
