import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import { Badge, Group, Text } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'
import { Dashboard } from './Dashboard'
import { LandingPage } from './LandingPage'

function ApiStatus() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/health')
      if (error) throw new Error('Health check failed')
      return data
    },
  })

  return (
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
  )
}

export function HomePage() {
  const { isAuthenticated } = useKindeAuth()

  if (!isAuthenticated) return <LandingPage />
  return <Dashboard footer={<ApiStatus />} />
}
