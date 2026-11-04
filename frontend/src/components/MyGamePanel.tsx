import { Card, Group, Loader, Stack, Text, Title } from '@mantine/core'

import { useMyGames } from '../api/collection'
import type { GameSummary } from '../api/games'
import { GameAnswersEditor } from './GameAnswersEditor'
import { RemoveGameButton } from './RemoveGameButton'
import { blankUserGame, expansionsInList } from './userGameFields'

/** Everything you've recorded about a game, editable; any answer adds it to your games. */
export function MyGamePanel({ game }: { game: GameSummary }) {
  const games = useMyGames()
  const row = games.data?.find((r) => r.game.id === game.id)

  return (
    <Card withBorder>
      <Stack gap="sm">
        <Group justify="space-between">
          <Title order={4}>My games</Title>
          {row && (
            <RemoveGameButton
              game={row.game}
              expansions={expansionsInList(row.game, games.data ?? [])}
              variant="text"
            />
          )}
        </Group>
        {games.isPending ? (
          <Loader size="sm" />
        ) : (
          <>
            {!row && (
              <Text size="sm" c="dimmed">
                Not in your games yet. Any answer below adds it.
              </Text>
            )}
            <GameAnswersEditor row={row ?? blankUserGame(game)} full />
          </>
        )}
      </Stack>
    </Card>
  )
}
