import { Badge, Card, Group, Image, Stack, Text } from '@mantine/core'
import { Link } from 'react-router'

import type { GameSummary } from '../api/games'
import { bestWithLabel, playersLabel, playtimeLabel, weightLabel } from './gameFacts'

export function GameCard({ game }: { game: GameSummary }) {
  const facts = [playersLabel(game), playtimeLabel(game), weightLabel(game)].filter(Boolean)
  const best = bestWithLabel(game)

  return (
    <Card component={Link} to={`/games/${game.id}`} withBorder padding="sm">
      <Group wrap="nowrap" align="flex-start">
        <Image
          src={game.thumbnail_url}
          alt=""
          w={64}
          h={64}
          radius="sm"
          fit="contain"
          fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E"
          bg="var(--mantine-color-default-hover)"
        />
        <Stack gap={4} style={{ minWidth: 0 }}>
          <Group gap="xs">
            <Text fw={600} lineClamp={2}>
              {game.name}
              {game.year_published && (
                <Text span c="dimmed" fw={400}>
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
          {facts.length > 0 && (
            <Text size="sm" c="dimmed">
              {facts.join(' · ')}
            </Text>
          )}
          {best && (
            <Badge size="sm" variant="light" w="fit-content">
              {best}
            </Badge>
          )}
        </Stack>
      </Group>
    </Card>
  )
}
