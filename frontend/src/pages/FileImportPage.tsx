import {
  Accordion,
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Center,
  Checkbox,
  FileInput,
  Group,
  Image,
  Loader,
  Radio,
  Select,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { useState } from 'react'
import { Link } from 'react-router'

import type { ImportPreview, ImportResult, UserGameUpdate } from '../api/collection'
import {
  type FileColumns,
  type FileImport,
  type FileRow,
  type GameBrief,
  type ImportColumn,
  useFileColumns,
  useFilePreview,
  useMatchFile,
  type WholeFile,
} from '../api/fileImport'
import { GameSearchSelect } from '../components/GameSearchSelect'
import { PreviewView, ResultView } from '../components/ImportPreview'
import { plural } from '../components/userGameFields'

const COLUMN_OPTIONS: { value: ImportColumn; label: string }[] = [
  { value: 'name', label: 'Game name' },
  { value: 'year', label: 'Year published' },
  { value: 'bgg_id', label: 'BGG id' },
  { value: 'ownership', label: 'Ownership' },
  { value: 'wishlist_priority', label: 'Wishlist' },
  { value: 'want_to_play', label: 'Want to play' },
  { value: 'rating', label: 'Your rating (1–10)' },
  { value: 'weight_vote', label: 'Your weight (1–5)' },
  { value: 'playtime_feel', label: 'Length (shorter / just right / longer)' },
  { value: 'can_teach', label: 'Can teach' },
  { value: 'teach_minutes', label: 'Teach time (minutes)' },
  { value: 'plays', label: 'Plays' },
  { value: 'will_bring', label: 'Will bring' },
  { value: 'notes', label: 'Notes (several columns allowed)' },
]
const IGNORE = 'ignore'

function GameLine({ game }: { game: GameBrief }) {
  return (
    <Group gap="xs" wrap="nowrap">
      <Image
        src={game.thumbnail_url}
        alt=""
        w={32}
        h={32}
        radius="sm"
        fit="contain"
        fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E"
        bg="var(--mantine-color-default-hover)"
      />
      <Text size="sm" fw={600}>
        {game.name}
        {game.year_published && (
          <Text span c="dimmed" fw={400} inherit>
            {' '}
            ({game.year_published})
          </Text>
        )}
      </Text>
      {game.is_expansion && (
        <Badge size="xs" variant="light" color="grape">
          Expansion
        </Badge>
      )}
    </Group>
  )
}

// ---- Step 2: say what each column holds ----

function ColumnsStep({
  layout,
  busy,
  error,
  onMatch,
  onRestart,
}: {
  layout: FileColumns
  busy: boolean
  error: string | null
  onMatch: (columns: (ImportColumn | null)[], wholeFile: WholeFile | null) => void
  onRestart: () => void
}) {
  const [columns, setColumns] = useState<(ImportColumn | null)[]>(layout.suggested)
  const [wholeFile, setWholeFile] = useState<WholeFile | null>(null)

  const chosen = columns.filter((c): c is ImportColumn => c !== null && c !== 'notes')
  const repeated = new Set(chosen.filter((c, i) => chosen.indexOf(c) !== i))
  const hasGame = columns.includes('name') || columns.includes('bgg_id')
  const hasShelf = columns.includes('ownership') || columns.includes('wishlist_priority')
  const ready = hasGame && repeated.size === 0 && (hasShelf || wholeFile !== null)

  return (
    <Stack>
      <Text>
        {plural(layout.row_count, 'row')} found. Say what each column holds; anything set to Ignore
        is left out.
      </Text>
      <Table withTableBorder verticalSpacing="xs">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Column</Table.Th>
            <Table.Th>Sample values</Table.Th>
            <Table.Th>Holds</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {layout.headers.map((header, i) => {
            const samples = layout.samples
              .map((row) => row[i])
              .filter(Boolean)
              .slice(0, 3)
            const column = columns[i]
            return (
              <Table.Tr key={i}>
                <Table.Td fw={600}>{header}</Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed" lineClamp={2}>
                    {samples.length ? samples.join(' · ') : '(empty)'}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Select
                    aria-label={`What ${header} holds`}
                    size="xs"
                    w={240}
                    allowDeselect={false}
                    data={[{ value: IGNORE, label: 'Ignore' }, ...COLUMN_OPTIONS]}
                    value={column ?? IGNORE}
                    error={column && repeated.has(column) ? 'Already used by another column' : null}
                    onChange={(value) =>
                      setColumns((current) =>
                        current.map((c, j) =>
                          j === i ? (value === IGNORE ? null : (value as ImportColumn)) : c,
                        ),
                      )
                    }
                  />
                </Table.Td>
              </Table.Tr>
            )
          })}
        </Table.Tbody>
      </Table>
      {!hasGame && (
        <Text size="sm" c="orange">
          Pick the column with the game&apos;s name (or its BGG id).
        </Text>
      )}
      {!hasShelf && (
        <Radio.Group
          label="No column says whether you own these games. Every game in this file is:"
          value={wholeFile}
          onChange={(value) => setWholeFile(value as WholeFile)}
        >
          <Group mt="xs">
            <Radio value="owned" label="Owned" />
            <Radio value="wishlist" label="On my wishlist" />
            <Radio value="neither" label="Neither (just add them)" />
          </Group>
        </Radio.Group>
      )}
      {error && <Alert color="red">{error}</Alert>}
      <Group>
        <Button disabled={!ready} loading={busy} onClick={() => onMatch(columns, wholeFile)}>
          Match games
        </Button>
        <Button variant="default" onClick={onRestart}>
          Choose a different file
        </Button>
      </Group>
    </Stack>
  )
}

// ---- Step 3: check the matches ----

interface RowState {
  pick: GameBrief | null
  skip: boolean
  /** Picked automatically or by the user, as opposed to an unchecked suggestion. */
  confirmed: boolean
}

function initialState(row: FileRow): RowState {
  return {
    pick: row.status === 'matched' ? row.match : null,
    skip: false,
    confirmed: row.status === 'matched',
  }
}

function RowCard({
  row,
  state,
  onChange,
}: {
  row: FileRow
  state: RowState
  onChange: (state: RowState) => void
}) {
  const fromFile = row.name ?? `BGG id ${row.bgg_id}`
  const suggestions = row.status === 'review' ? row.candidates.slice(0, 3) : []
  return (
    <Card withBorder padding="xs" opacity={state.skip ? 0.5 : 1}>
      <Stack gap={6}>
        <Group justify="space-between" wrap="nowrap" align="flex-start">
          <Stack gap={2}>
            <Text size="sm">
              {row.line > 0 && (
                <Text span c="dimmed" inherit>
                  Row {row.line}:{' '}
                </Text>
              )}
              “{fromFile}”{row.year ? ` (${row.year})` : ''}
            </Text>
            {row.problems.map((p) => (
              <Text key={p} size="xs" c="orange">
                {p}
              </Text>
            ))}
          </Stack>
          <Checkbox
            size="xs"
            label="Skip"
            checked={state.skip}
            onChange={(e) => onChange({ ...state, skip: e.currentTarget.checked })}
          />
        </Group>
        {state.pick && state.confirmed ? (
          <GameLine game={state.pick} />
        ) : (
          <Text size="sm" c="dimmed">
            {suggestions.length ? 'Which game is it?' : 'No close match. Search for it below.'}
          </Text>
        )}
        {!state.confirmed && suggestions.length > 0 && (
          <Group gap="xs">
            {suggestions.map((c) => (
              <Button
                key={c.game.id}
                size="compact-xs"
                variant="light"
                onClick={() => onChange({ pick: c.game, skip: false, confirmed: true })}
              >
                {c.game.name}
                {c.game.year_published ? ` (${c.game.year_published})` : ''}
              </Button>
            ))}
          </Group>
        )}
        <GameSearchSelect
          ariaLabel={`Search BGG for ${fromFile}`}
          onPick={(game) => onChange({ pick: game, skip: false, confirmed: true })}
        />
      </Stack>
    </Card>
  )
}

function ReviewStep({
  result,
  busy,
  error,
  onPreview,
  onBack,
}: {
  result: FileImport
  busy: boolean
  error: string | null
  onPreview: (games: { gameId: number; values: UserGameUpdate }[]) => void
  onBack: () => void
}) {
  const [states, setStates] = useState(() => result.rows.map(initialState))
  const set = (i: number, state: RowState) =>
    setStates((current) => current.map((s, j) => (j === i ? state : s)))

  const indexed = result.rows.map((row, i) => ({ row, i }))
  // Rows stay in the section they started in, so they don't jump around while being fixed.
  const needsLook = indexed.filter(({ row }) => row.status !== 'matched')
  const matched = indexed.filter(({ row }) => row.status === 'matched')
  const resolved = needsLook.filter(({ i }) => states[i].confirmed || states[i].skip).length
  const games = indexed
    .filter(({ i }) => states[i].confirmed && states[i].pick && !states[i].skip)
    .map(({ row, i }) => ({ gameId: states[i].pick!.id, values: row.values as UserGameUpdate }))

  const leftOut = result.rows.length - games.length

  return (
    <Stack>
      <Text>
        {plural(matched.length, 'row')} matched a game.{' '}
        {needsLook.length > 0 &&
          `${plural(needsLook.length, 'row')} need a look (${resolved} done).`}
      </Text>
      <Accordion
        multiple
        variant="separated"
        defaultValue={needsLook.length ? ['look'] : ['matched']}
      >
        {needsLook.length > 0 && (
          <Accordion.Item value="look">
            <Accordion.Control>Need a look ({needsLook.length})</Accordion.Control>
            <Accordion.Panel>
              <Stack gap="xs">
                {needsLook.map(({ row, i }) => (
                  <RowCard key={i} row={row} state={states[i]} onChange={(s) => set(i, s)} />
                ))}
              </Stack>
            </Accordion.Panel>
          </Accordion.Item>
        )}
        {matched.length > 0 && (
          <Accordion.Item value="matched">
            <Accordion.Control>Matched ({matched.length})</Accordion.Control>
            <Accordion.Panel>
              <Stack gap="xs">
                {matched.map(({ row, i }) => (
                  <RowCard key={i} row={row} state={states[i]} onChange={(s) => set(i, s)} />
                ))}
              </Stack>
            </Accordion.Panel>
          </Accordion.Item>
        )}
      </Accordion>
      {leftOut > 0 && (
        <Text size="sm" c="dimmed">
          {plural(leftOut, 'row')} without a game (or skipped) will be left out.
        </Text>
      )}
      {error && <Alert color="red">{error}</Alert>}
      <Group>
        <Button disabled={games.length === 0} loading={busy} onClick={() => onPreview(games)}>
          Preview changes for {plural(games.length, 'game')}
        </Button>
        <Button variant="default" onClick={onBack}>
          Back to columns
        </Button>
      </Group>
    </Stack>
  )
}

// ---- The page ----

export function FileImportPage() {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)
  const columns = useFileColumns()
  const match = useMatchFile()
  const previewing = useFilePreview()
  const isBggExport = columns.data?.kind === 'bgg_export'

  const restart = () => {
    setFile(null)
    setPreview(null)
    setResult(null)
    columns.reset()
    match.reset()
    previewing.reset()
  }
  const choose = (chosen: File | null) => {
    restart()
    if (!chosen) return
    setFile(chosen)
    columns.mutate(chosen, {
      // A BGG export's columns are known, and its rows all carry BGG ids: straight to preview.
      onSuccess: (layout) => {
        if (layout.kind !== 'bgg_export') return
        match.mutate(
          { file: chosen, columns: [], wholeFile: null },
          {
            onSuccess: (matched) =>
              previewing.mutate(
                {
                  wholeBggCollection: true,
                  games: matched.rows
                    .filter((r) => r.match)
                    .map((r) => ({ gameId: r.match!.id, values: r.values as UserGameUpdate })),
                },
                { onSuccess: setPreview },
              ),
          },
        )
      },
    })
  }

  const working = columns.isPending || (isBggExport && (match.isPending || previewing.isPending))

  let body
  if (result) {
    body = <ResultView result={result} onAgain={restart} againLabel="Import another file" />
  } else if (preview) {
    body = <PreviewView preview={preview} source="file" onApplied={setResult} />
  } else if (working) {
    body = (
      <Center py="xl">
        <Stack align="center" gap="xs">
          <Loader />
          <Text c="dimmed" size="sm">
            Reading {file?.name}…
          </Text>
        </Stack>
      </Center>
    )
  } else if (file && match.isSuccess && !isBggExport) {
    body = (
      <ReviewStep
        key={match.submittedAt}
        result={match.data}
        busy={previewing.isPending}
        error={previewing.error?.message ?? null}
        onPreview={(games) =>
          previewing.mutate({ games, wholeBggCollection: false }, { onSuccess: setPreview })
        }
        onBack={() => match.reset()}
      />
    )
  } else if (file && columns.isSuccess && !isBggExport) {
    body = (
      <ColumnsStep
        layout={columns.data}
        busy={match.isPending}
        error={match.error?.message ?? null}
        onMatch={(chosen, wholeFile) => match.mutate({ file, columns: chosen, wholeFile })}
        onRestart={restart}
      />
    )
  } else {
    const error = columns.error ?? match.error ?? previewing.error
    body = (
      <Stack align="flex-start">
        <Text>
          Upload a spreadsheet or list of your games: Excel, CSV, or a text file with one name per
          line. You&apos;ll say what each column holds, check the matches, and see every change
          before anything is saved.
        </Text>
        <Text size="sm" c="dimmed">
          BGG&apos;s own collection export works too. Starting from scratch?{' '}
          <Anchor href="/game-list-template.csv" download>
            Download a template
          </Anchor>
          .
        </Text>
        {error && <Alert color="red">{error.message}</Alert>}
        <FileInput
          label="Your game list"
          placeholder="Choose a file"
          accept=".xlsx,.xlsm,.csv,.tsv,.txt"
          value={file}
          onChange={choose}
          w={{ base: '100%', sm: 360 }}
        />
      </Stack>
    )
  }

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Import a game list</Title>
        <Button component={Link} to="/collection" variant="default">
          My games
        </Button>
      </Group>
      {body}
    </Stack>
  )
}
