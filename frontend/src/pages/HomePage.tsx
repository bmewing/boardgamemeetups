import { Badge, Group, Stack, Text, Title } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'

export function HomePage() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/health')
      if (error) throw new Error('Health check failed')
      return data
    },
  })

  return (
    <Stack>
      <Title order={2}>Welcome</Title>
      <Text>Organize game nights, see who's coming, and pick what to play.</Text>
      <Group gap="xs">
        <Text size="sm" c="dimmed">
          API status:
        </Text>
        {health.isPending && <Badge color="gray">checking…</Badge>}
        {health.isError && <Badge color="red">unreachable</Badge>}
        {health.data && (
          <Badge color={health.data.status === 'ok' ? 'green' : 'yellow'}>
            {health.data.status} · database {health.data.database}
          </Badge>
        )}
      </Group>
    </Stack>
  )
}
