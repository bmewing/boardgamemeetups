import { Alert, Anchor, Button, Center, Loader, Stack, Text, Title } from '@mantine/core'
import { useState } from 'react'
import { Link } from 'react-router'

import { type ImportResult, useBggPullPreview } from '../api/collection'
import { useMe } from '../api/me'
import { PreviewView, ResultView } from '../components/ImportPreview'

export function BggPullPage() {
  const me = useMe()
  const pull = useBggPullPreview()
  const [result, setResult] = useState<ImportResult | null>(null)
  const start = () => {
    setResult(null)
    pull.mutate()
  }

  let body
  if (me.isPending) {
    body = <Loader />
  } else if (me.isError) {
    body = <Alert color="red">{me.error.message}</Alert>
  } else if (!me.data.bgg_username) {
    body = (
      <Alert title="Add your BGG username first">
        Pulling needs to know whose collection to read.{' '}
        <Anchor component={Link} to="/profile">
          Set it on your profile.
        </Anchor>
      </Alert>
    )
  } else if (result) {
    body = <ResultView result={result} onAgain={start} againLabel="Pull again" />
  } else if (pull.isPending) {
    body = (
      <Center py="xl">
        <Stack align="center" gap="xs">
          <Loader />
          <Text c="dimmed" size="sm">
            Asking BoardGameGeek… big collections can take up to a minute.
          </Text>
        </Stack>
      </Center>
    )
  } else if (pull.isSuccess) {
    body = (
      <PreviewView key={pull.submittedAt} preview={pull.data} source="bgg" onApplied={setResult} />
    )
  } else {
    const last = me.data.bgg_pulled_at
    body = (
      <Stack align="flex-start">
        <Text>
          This reads the BGG collection for <b>{me.data.bgg_username}</b> and shows every change
          before anything is saved. Nothing is ever sent back to BGG.
        </Text>
        {last && (
          <Text size="sm" c="dimmed">
            Last pulled {new Date(last).toLocaleString()}.
          </Text>
        )}
        {pull.isError && <Alert color="red">{pull.error.message}</Alert>}
        <Button onClick={start}>{pull.isError ? 'Try again' : 'Fetch from BGG'}</Button>
      </Stack>
    )
  }

  return (
    <Stack>
      <Title order={2}>Pull from BoardGameGeek</Title>
      {body}
    </Stack>
  )
}
