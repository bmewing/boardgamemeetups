import { Anchor, Badge, Card, Group, Image, type MantineSpacing, Stack, Text } from '@mantine/core'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { GameSummary } from '../api/games'
import { bestWithLabel, playersLabel, playtimeLabel, weightLabel } from './gameFacts'

/**
 * A game in a list; `children` adds lines under the game's facts (e.g. your answers), and
 * `pr` leaves room on the right for a control laid over the card.
 *
 * `below` goes under the whole card's top row, full width. When it's given, only the image
 * and name link to the game's page, so controls in it can be used without navigating.
 */
export function GameCard({
  game,
  children,
  below,
  pr,
}: {
  game: GameSummary
  children?: ReactNode
  below?: ReactNode
  pr?: MantineSpacing
}) {
  const facts = [playersLabel(game), playtimeLabel(game), weightLabel(game)].filter(Boolean)
  const best = bestWithLabel(game)
  const href = `/games/${game.id}`
  const wholeCardLinks = below === undefined

  const image = (
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
  )
  const name = (
    <Text fw={600} lineClamp={2}>
      {game.name}
      {game.year_published && (
        <Text span c="dimmed" fw={400}>
          {' '}
          ({game.year_published})
        </Text>
      )}
    </Text>
  )

  const top = (
    <Group wrap="nowrap" align="flex-start">
      {wholeCardLinks ? (
        image
      ) : (
        <Link to={href} tabIndex={-1} aria-hidden style={{ flexShrink: 0 }}>
          {image}
        </Link>
      )}
      <Stack gap={4} style={{ minWidth: 0 }}>
        <Group gap="xs">
          {wholeCardLinks ? (
            name
          ) : (
            <Anchor component={Link} to={href} c="inherit">
              {name}
            </Anchor>
          )}
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
        {children}
      </Stack>
    </Group>
  )

  if (wholeCardLinks) {
    return (
      <Card component={Link} to={href} withBorder padding="sm" pr={pr}>
        {top}
      </Card>
    )
  }
  return (
    <Card withBorder padding="sm" pr={pr}>
      <Stack gap="sm">
        {top}
        {below}
      </Stack>
    </Card>
  )
}
