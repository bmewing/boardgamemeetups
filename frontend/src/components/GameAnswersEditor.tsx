import {
  Alert,
  Button,
  Checkbox,
  Group,
  Indicator,
  Input,
  MultiSelect,
  NumberInput,
  Select,
  Stack,
  Text,
  Textarea,
  Tooltip,
} from '@mantine/core'
import { type Ref, useRef, useState } from 'react'

import {
  type Ownership,
  type UserGame,
  type UserGameUpdate,
  useMoods,
  useUpdateMyGame,
} from '../api/collection'
import { playtimeLabel } from './gameFacts'
import { isOwned, OWNERSHIP_LABELS, teaches, WISHLIST_LABELS } from './userGameFields'

const OWNERSHIP_OPTIONS = Object.entries(OWNERSHIP_LABELS).map(([value, label]) => ({
  value,
  label,
}))
const WISHLIST_OPTIONS = Object.entries(WISHLIST_LABELS).map(([value, label]) => ({
  value,
  label: `${value} · ${label}`,
}))

type Vote = UserGame['player_counts'][number]['vote']
type PlaytimeFeel = NonNullable<UserGame['playtime_feel']>

// A tap moves a count along this cycle; the first tap on a blank count says "best".
const NEXT_VOTE: Record<Vote | 'blank', Vote | null> = {
  blank: 'best',
  best: 'recommended',
  recommended: 'not_recommended',
  not_recommended: null,
}
const VOTE_LOOK: Record<Vote, { color: string; variant: string; label: string }> = {
  best: { color: 'green', variant: 'filled', label: 'best' },
  recommended: { color: 'blue', variant: 'light', label: 'recommended' },
  not_recommended: { color: 'red', variant: 'light', label: 'not recommended' },
}
// More buttons than this in a row stops being quick to scan.
const MAX_COUNTS_SHOWN = 12

// BGG's own weight scale.
const WEIGHT_OPTIONS = [
  { value: '1', label: '1 · Light' },
  { value: '2', label: '2 · Medium light' },
  { value: '3', label: '3 · Medium' },
  { value: '4', label: '4 · Medium heavy' },
  { value: '5', label: '5 · Heavy' },
]
const PLAYTIME_OPTIONS: { value: PlaytimeFeel; label: string }[] = [
  { value: 'shorter', label: 'Shorter' },
  { value: 'just_right', label: 'As listed' },
  { value: 'longer', label: 'Longer' },
]

/** The counts to offer: the box's range (capped), plus any count you've already voted on. */
function countsToShow(row: UserGame): number[] {
  const { min_players: min, max_players: max } = row.game
  const counts = new Set(row.player_counts.map((pc) => pc.players))
  if (min && max) {
    for (let n = min; n <= Math.min(max, min + MAX_COUNTS_SHOWN - 1); n++) counts.add(n)
  }
  return [...counts].sort((a, b) => a - b)
}

function PlayerCounts({ row, save }: { row: UserGame; save: (c: UserGameUpdate) => void }) {
  const counts = countsToShow(row)
  if (counts.length === 0) return null
  const votes = new Map(row.player_counts.map((pc) => [pc.players, pc.vote]))
  const bggBest = new Set(row.game.best_with)

  const tap = (players: number) => {
    const next = NEXT_VOTE[votes.get(players) ?? 'blank']
    const rest = row.player_counts.filter((pc) => pc.players !== players)
    save({ player_counts: next ? [...rest, { players, vote: next }] : rest })
  }

  return (
    <Input.Wrapper label="Optimal player count" size="xs">
      <Group gap={4}>
        {counts.map((n) => {
          const vote = votes.get(n)
          const look = vote ? VOTE_LOOK[vote] : null
          const bgg = bggBest.has(n)
          return (
            <Tooltip
              key={n}
              label={`Tap to change.${bgg ? ' The dot: BGG says best.' : ''}`}
              openDelay={600}
            >
              <Indicator size={7} color="meeple" offset={3} disabled={!bgg}>
                <Button
                  size="compact-sm"
                  miw={32}
                  px={6}
                  color={look?.color}
                  variant={look?.variant ?? 'default'}
                  td={vote === 'not_recommended' ? 'line-through' : undefined}
                  aria-label={`${n} players: ${look?.label ?? 'no answer'}${bgg ? " (BGG's best)" : ''}`}
                  onClick={() => tap(n)}
                >
                  {n}
                </Button>
              </Indicator>
            </Tooltip>
          )
        })}
      </Group>
    </Input.Wrapper>
  )
}

/**
 * A number box that saves when you leave it (or press Enter), not on every keystroke.
 * Clearing it saves null.
 */
function SavedNumber({
  value,
  onSave,
  error,
  inputRef,
  ...props
}: {
  value: number | null
  onSave: (value: number | null) => void
  label: string
  placeholder?: string
  min: number
  max: number
  step?: number
  decimalScale?: number
  w: number
  error?: string
  inputRef?: Ref<HTMLInputElement>
  allowDecimal?: boolean
  'aria-label'?: string
}) {
  const [draft, setDraft] = useState<string | number>(value ?? '')
  const [seen, setSeen] = useState(value)
  // Follow saved changes from elsewhere (e.g. an import) when not mid-edit.
  if (seen !== value) {
    setSeen(value)
    setDraft(value ?? '')
  }

  const commit = () => {
    const next = draft === '' ? null : Number(draft)
    if (next !== null && Number.isNaN(next)) return setDraft(value ?? '')
    if (next !== value) onSave(next)
  }

  return (
    <NumberInput
      size="xs"
      value={draft}
      onChange={setDraft}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === 'Enter') e.currentTarget.blur()
      }}
      clampBehavior="blur"
      hideControls
      error={error}
      ref={inputRef}
      {...props}
    />
  )
}

/** Free text that saves when you leave the box; clearing it saves null. */
function SavedText({
  value,
  onSave,
}: {
  value: string | null
  onSave: (v: string | null) => void
}) {
  const [draft, setDraft] = useState(value ?? '')
  const [seen, setSeen] = useState(value)
  if (seen !== value) {
    setSeen(value)
    setDraft(value ?? '')
  }
  return (
    <Textarea
      size="xs"
      label="Notes"
      placeholder="Only you see these"
      autosize
      minRows={2}
      maxLength={2000}
      value={draft}
      onChange={(e) => setDraft(e.currentTarget.value)}
      onBlur={() => {
        const next = draft.trim() || null
        if (next !== value) onSave(next)
      }}
    />
  )
}

/** Ownership, wishlist, plays and notes: on the game's own page, not in list rows. */
function StatusFields({ row, save }: { row: UserGame; save: (c: UserGameUpdate) => void }) {
  return (
    <Group gap="sm" align="flex-start">
      <Select
        size="xs"
        label="Ownership"
        placeholder="Don't own it"
        data={OWNERSHIP_OPTIONS}
        value={row.ownership}
        onChange={(v) => save({ ownership: v as Ownership | null })}
        clearable
        w={150}
      />
      <Select
        size="xs"
        label="Wishlist"
        placeholder="Not on it"
        data={WISHLIST_OPTIONS}
        value={row.wishlist_priority?.toString() ?? null}
        onChange={(v) => save({ wishlist_priority: v ? Number(v) : null })}
        clearable
        w={170}
      />
      <SavedNumber
        label="Plays"
        value={row.plays}
        // Plays can't be blank; clearing the box means none.
        onSave={(plays) => save({ plays: plays ?? 0 })}
        min={0}
        max={100_000}
        allowDecimal={false}
        w={70}
      />
    </Group>
  )
}

/**
 * Every answer about one of your games, edited in place; each change saves on its own.
 * `full` adds ownership, wishlist, plays and notes, for the game's own page. A game not in
 * your list yet can be given a blank row: any answer adds it.
 */
export function GameAnswersEditor({ row, full = false }: { row: UserGame; full?: boolean }) {
  const update = useUpdateMyGame()
  const moods = useMoods()
  const save = (changes: UserGameUpdate) =>
    update.mutate({ gameId: row.game.id, changes, game: row.game })
  // Ticked "Can teach" without a teach time yet: held here until the time is given.
  const [needsTeachTime, setNeedsTeachTime] = useState(false)
  const teachInput = useRef<HTMLInputElement>(null)
  const g = row.game

  const moodOptions = (moods.data ?? [])
    .filter((m) => m.taggable)
    .map((m) => ({ value: m.id, label: m.name }))

  return (
    <Stack gap="xs">
      {full && <StatusFields row={row} save={save} />}
      <Group gap="sm" align="flex-start">
        <PlayerCounts row={row} save={save} />
        <SavedNumber
          label="Rating"
          placeholder={g.bgg_rating ? `BGG ${g.bgg_rating.toFixed(1)}` : '1–10'}
          value={row.rating}
          onSave={(rating) => save({ rating })}
          min={1}
          max={10}
          step={0.5}
          decimalScale={2}
          w={76}
        />
        <Select
          size="xs"
          label="Weight"
          placeholder={g.weight ? `BGG ${g.weight.toFixed(1)}` : '—'}
          data={WEIGHT_OPTIONS}
          value={row.weight_vote?.toString() ?? null}
          onChange={(v) => save({ weight_vote: v ? Number(v) : null })}
          clearable
          w={150}
        />
        <Select
          size="xs"
          label="Length vs. listed"
          placeholder={playtimeLabel(g) ?? '—'}
          data={PLAYTIME_OPTIONS}
          value={row.playtime_feel}
          onChange={(v) => save({ playtime_feel: v as PlaytimeFeel | null })}
          clearable
          w={120}
        />
        <Stack gap={4}>
          <Checkbox
            size="xs"
            label="Can teach"
            // Owners start ticked until they say otherwise.
            checked={teaches(row) || needsTeachTime}
            onChange={(e) => {
              const checked = e.currentTarget.checked
              if (!checked) {
                setNeedsTeachTime(false)
                if (teaches(row)) save({ can_teach: false })
              } else if (row.teach_minutes) {
                save({ can_teach: true })
              } else {
                setNeedsTeachTime(true)
                teachInput.current?.focus()
              }
            }}
          />
          <SavedNumber
            label=""
            aria-label="Teach time in minutes"
            placeholder="Teach min"
            value={row.teach_minutes}
            onSave={(minutes) => {
              setNeedsTeachTime(false)
              // A teach time means you can teach it; clearing it means you can't.
              save(
                minutes === null
                  ? { can_teach: false, teach_minutes: null }
                  : { can_teach: true, teach_minutes: minutes },
              )
            }}
            error={needsTeachTime ? 'How long?' : undefined}
            inputRef={teachInput}
            min={1}
            max={24 * 60}
            allowDecimal={false}
            w={90}
          />
        </Stack>
        <Stack gap={6} pt={4}>
          <Checkbox
            size="xs"
            label="Want to play"
            checked={row.want_to_play}
            onChange={(e) => save({ want_to_play: e.currentTarget.checked })}
          />
          {isOwned(row) && (
            <Checkbox
              size="xs"
              label="Will bring"
              checked={row.will_bring}
              onChange={(e) => save({ will_bring: e.currentTarget.checked })}
            />
          )}
        </Stack>
      </Group>
      {full && (
        <Text size="xs" c="dimmed">
          Player counts: tap for best → recommended → not recommended → no answer. A dot marks
          BGG&apos;s best.
        </Text>
      )}
      {moodOptions.length > 0 && (
        <MultiSelect
          size="xs"
          aria-label="Moods"
          placeholder={row.moods.length ? undefined : 'Moods'}
          data={moodOptions}
          value={row.moods}
          onChange={(ids) => save({ moods: ids })}
          hidePickedOptions
          clearable
          maw={420}
        />
      )}
      {full && <SavedText value={row.notes} onSave={(notes) => save({ notes })} />}
      {update.isError && (
        <Alert color="red" p="xs">
          {update.error.message}
        </Alert>
      )}
    </Stack>
  )
}
