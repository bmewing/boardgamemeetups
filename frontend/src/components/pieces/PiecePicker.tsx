import { Alert, Group, Stack, Text, Title, UnstyledButton } from '@mantine/core'

import type { UserProfile } from '../../api/client'
import { useUpdateMe } from '../../api/me'
import classes from './PiecePicker.module.css'
import { pieceOf } from './pieceOf'
import { PieceDrawing } from './PlayerPiece'
import { PIECE_COLORS, PIECE_GROUPS, PIECES, type PieceColorName } from './shapes'

const COLORS = Object.entries(PIECE_COLORS) as [
  PieceColorName,
  (typeof PIECE_COLORS)[PieceColorName],
][]

/** Pick a piece, then a color; each choice saves as soon as it's made. */
export function PiecePicker({ profile }: { profile: UserProfile }) {
  const update = useUpdateMe()
  // While a pick is saving, show it rather than the one it replaces.
  const { piece, color } = pieceOf({ ...profile, ...(update.isPending ? update.variables : {}) })

  return (
    <Stack gap="sm">
      <Title order={4}>Your piece</Title>
      <Group gap="md" wrap="nowrap" align="center">
        <PieceDrawing piece={piece} color={color} size={72} className={classes.preview} />
        <Text size="sm" c="dimmed">
          This stands for you around the table: on meetups, in your groups, and up in the corner.
        </Text>
      </Group>

      {PIECE_GROUPS.map((group) => (
        <div key={group.label}>
          <Text size="xs" fw={600} c="dimmed" tt="uppercase" mb={4}>
            {group.label}
          </Text>
          <div className={classes.pieces} role="radiogroup" aria-label={group.label}>
            {group.pieces.map((name) => (
              <UnstyledButton
                key={name}
                className={classes.choice}
                role="radio"
                aria-checked={name === piece}
                aria-label={PIECES[name].label}
                title={PIECES[name].label}
                data-selected={name === piece || undefined}
                onClick={() => update.mutate({ piece: name })}
              >
                <PieceDrawing piece={name} color={color} size={40} label="" />
              </UnstyledButton>
            ))}
          </div>
        </div>
      ))}

      <div>
        <Text size="xs" fw={600} c="dimmed" tt="uppercase" mb={4}>
          Color
        </Text>
        <div className={classes.colors} role="radiogroup" aria-label="Color">
          {COLORS.map(([name, { label, hex }]) => (
            <UnstyledButton
              key={name}
              className={classes.swatch}
              role="radio"
              aria-checked={name === color}
              aria-label={label}
              title={label}
              data-selected={name === color || undefined}
              onClick={() => update.mutate({ piece_color: name })}
              style={{ background: hex }}
            />
          ))}
        </div>
      </div>
      {update.isError && <Alert color="red">{update.error.message}</Alert>}
    </Stack>
  )
}
