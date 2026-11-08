import { Alert, Group, Stack, Text, Title, UnstyledButton } from '@mantine/core'
import { useState } from 'react'

import type { UserProfile } from '../../api/client'
import { useUpdateMe } from '../../api/me'
import { LockBadge } from '../achievements/LockBadge'
import classes from './PiecePicker.module.css'
import { pieceOf } from './pieceOf'
import { PieceDrawing } from './PlayerPiece'
import {
  ACHIEVEMENTS,
  type AchievementName,
  PIECE_COLORS,
  PIECE_GROUPS,
  PIECE_LABELS,
  type PieceColorName,
  type PieceName,
} from './shapes'

const COLORS = Object.entries(PIECE_COLORS) as [
  PieceColorName,
  (typeof PIECE_COLORS)[PieceColorName],
][]

type Lockable = { unlocked: boolean; unlocked_by: AchievementName | null }

/** How to unlock something, or null if it's theirs to pick (or already theirs). */
function lockHint(state: Lockable | undefined, current: boolean): string | null {
  if (current || !state || state.unlocked || !state.unlocked_by) return null
  return ACHIEVEMENTS[state.unlocked_by].how
}

function lockedLabel(name: string, how: string | null): string {
  return how ? `${name} (locked: ${how.toLowerCase()} to unlock)` : name
}

/**
 * Pick a piece, then a color; each choice saves as soon as it's made. Most pieces and some
 * colors start locked, each until an achievement unlocks it; what you have stays yours.
 */
export function PiecePicker({ profile }: { profile: UserProfile }) {
  const update = useUpdateMe()
  // While a pick is saving, show it rather than the one it replaces.
  const { piece, color } = pieceOf({ ...profile, ...(update.isPending ? update.variables : {}) })
  const pieces = new Map(profile.pieces.map((state) => [state.piece as PieceName, state]))
  const colors = new Map(profile.colors.map((state) => [state.color as PieceColorName, state]))
  const fresh = new Set(profile.achievements.filter((a) => a.new).map((a) => a.achievement))
  const [hint, setHint] = useState<{ name: string; how: string } | null>(null)

  const unlocked =
    profile.pieces.filter((state) => state.unlocked).length +
    profile.colors.filter((state) => state.unlocked).length
  const total = profile.pieces.length + profile.colors.length

  return (
    <Stack gap="sm">
      <Group justify="space-between" align="baseline">
        <Title order={4}>Your piece</Title>
        <Text size="sm" c="dimmed">
          {unlocked} of {total} pieces and colors unlocked
        </Text>
      </Group>
      <Group gap="md" wrap="nowrap" align="center">
        <PieceDrawing piece={piece} color={color} size={72} className={classes.preview} />
        <Text size="sm" c="dimmed">
          This stands for you around the table: on meetups, in your groups, and up in the corner.
          Earn achievements to unlock more pieces and colors.
        </Text>
      </Group>

      {PIECE_GROUPS.map((group) => (
        <div key={group.label}>
          <Text size="xs" fw={600} c="dimmed" tt="uppercase" mb={4}>
            {group.label}
          </Text>
          <div className={classes.pieces} role="radiogroup" aria-label={group.label}>
            {group.pieces.map((name) => {
              const state = pieces.get(name)
              const how = lockHint(state, name === piece)
              const label = lockedLabel(PIECE_LABELS[name], how)
              return (
                <UnstyledButton
                  key={name}
                  className={classes.choice}
                  role="radio"
                  aria-checked={name === piece}
                  aria-disabled={how ? true : undefined}
                  aria-label={label}
                  title={label}
                  data-selected={name === piece || undefined}
                  data-locked={how ? true : undefined}
                  onClick={() => {
                    setHint(how ? { name: PIECE_LABELS[name], how } : null)
                    if (!how) update.mutate({ piece: name })
                  }}
                >
                  <PieceDrawing
                    piece={name}
                    color={color}
                    size={40}
                    label=""
                    className={how ? classes.lockedDrawing : undefined}
                  />
                  {how && <LockBadge />}
                  {state?.unlocked_by && fresh.has(state.unlocked_by) && (
                    <span className={classes.newBadge}>New</span>
                  )}
                </UnstyledButton>
              )
            })}
          </div>
        </div>
      ))}

      <div>
        <Text size="xs" fw={600} c="dimmed" tt="uppercase" mb={4}>
          Color
        </Text>
        <div className={classes.colors} role="radiogroup" aria-label="Color">
          {COLORS.map(([name, { label, hex }]) => {
            const state = colors.get(name)
            const how = lockHint(state, name === color && profile.piece_color === name)
            const full = lockedLabel(label, how)
            return (
              <UnstyledButton
                key={name}
                className={classes.swatch}
                role="radio"
                aria-checked={name === color}
                aria-disabled={how ? true : undefined}
                aria-label={full}
                title={full}
                data-selected={name === color || undefined}
                data-locked={how ? true : undefined}
                onClick={() => {
                  setHint(how ? { name: label, how } : null)
                  if (!how) update.mutate({ piece_color: name })
                }}
                style={{ background: hex }}
              >
                {how && <LockBadge />}
                {state?.unlocked_by && fresh.has(state.unlocked_by) && (
                  <span className={classes.newBadge}>New</span>
                )}
              </UnstyledButton>
            )
          })}
        </div>
      </div>
      {hint && (
        <Text size="sm" role="status">
          <b>{hint.name}</b> is locked. {hint.how} to unlock it.
        </Text>
      )}
      {update.isError && <Alert color="red">{update.error.message}</Alert>}
    </Stack>
  )
}
