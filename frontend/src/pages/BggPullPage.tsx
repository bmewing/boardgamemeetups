import { Alert, Anchor, Button, Stack, Text, Title } from '@mantine/core'
import { useState } from 'react'
import { Link } from 'react-router'

import { type ImportResult, useBggPullPreview } from '../api/collection'
import { useMe } from '../api/me'
import { ErrorNote, LoadingNote } from '../components/mascot/MascotNote'
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
    body = <LoadingNote />
  } else if (me.isError) {
    body = <ErrorNote error={me.error} onRetry={me.refetch} />
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
    body = <LoadingNote>Asking BoardGameGeek… big collections can take up to a minute.</LoadingNote>
  } else if (pull.isError) {
    body = <ErrorNote error={pull.error} onRetry={start} title="BoardGameGeek didn’t answer" />
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
        <Button onClick={start}>Fetch from BGG</Button>
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
