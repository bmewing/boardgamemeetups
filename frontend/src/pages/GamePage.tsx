import {
  Alert,
  Anchor,
  Badge,
  Center,
  Group,
  Image,
  Loader,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { Link, useParams } from 'react-router'

import { type GameDetail, useGame } from '../api/games'
import { bestWithLabel, playersLabel, playtimeLabel, weightLabel } from '../components/gameFacts'
import { MyGamePanel } from '../components/MyGamePanel'

function PlayerCountVotes({ game }: { game: GameDetail }) {
  if (game.player_count_votes.length === 0) return null
  const best = new Set(game.best_with.map(String))

  return (
    <Stack gap="xs">
      <Title order={4}>Community player count votes</Title>
      <Table striped withTableBorder fz="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Players</Table.Th>
            <Table.Th>Best</Table.Th>
            <Table.Th>Recommended</Table.Th>
            <Table.Th>Not recommended</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {game.player_count_votes.map((row) => (
            <Table.Tr key={row.players} fw={best.has(row.players) ? 700 : undefined}>
              <Table.Td>{row.players}</Table.Td>
              <Table.Td>{row.best}</Table.Td>
              <Table.Td>{row.recommended}</Table.Td>
              <Table.Td>{row.not_recommended}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Stack>
  )
}

export function GamePage() {
  const gameId = Number(useParams().gameId)
  const game = useGame(gameId)

  if (game.isPending) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    )
  }
  if (game.isError) return <Alert color="red">{game.error.message}</Alert>

  const g = game.data
  const facts = [
    playersLabel(g),
    playtimeLabel(g),
    g.min_age ? `Ages ${g.min_age}+` : null,
    weightLabel(g),
    g.bgg_rank ? `BGG rank #${g.bgg_rank}` : null,
  ].filter(Boolean)
  const best = bestWithLabel(g)

  return (
    <Stack>
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        {g.image_url && (
          <Image src={g.image_url} alt={g.name} radius="md" mah={360} fit="contain" />
        )}
        <Stack gap="xs">
          <Title order={2}>
            {g.name}
            {g.year_published && (
              <Text span c="dimmed" inherit fw={400}>
                {' '}
                ({g.year_published})
              </Text>
            )}
          </Title>
          {g.is_expansion && (
            <Group gap="xs">
              <Badge variant="light" color="grape">
                Expansion
              </Badge>
              {g.base_game_ids.map((id) => (
                <Anchor key={id} component={Link} to={`/games/${id}`} size="sm">
                  View base game
                </Anchor>
              ))}
            </Group>
          )}
          <Text c="dimmed">{facts.join(' · ')}</Text>
          {best && (
            <Badge variant="light" w="fit-content">
              {best}
            </Badge>
          )}
          {g.categories.length > 0 && (
            <Group gap={4}>
              {g.categories.map((c) => (
                <Badge key={c} variant="outline" size="sm" color="gray">
                  {c}
                </Badge>
              ))}
            </Group>
          )}
          {g.mechanics.length > 0 && (
            <Text size="sm" c="dimmed">
              {g.mechanics.join(', ')}
            </Text>
          )}
          <Anchor href={g.bgg_url} target="_blank" size="sm">
            View on BoardGameGeek
          </Anchor>
        </Stack>
      </SimpleGrid>
      <MyGamePanel game={g} />
      <PlayerCountVotes game={g} />
    </Stack>
  )
}
