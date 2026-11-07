import { Alert, Anchor, Button, Group, Stack, Text, Title } from '@mantine/core'
import { Link, useParams, useSearchParams } from 'react-router'

import { EMAIL_KINDS, emailKind, useEmailSettingsByLink, useUnsubscribe } from '../api/email'
import { ErrorNote, LoadingNote } from '../components/mascot/MascotNote'

/** Where an email's "stop these emails" link lands. Works without signing in. It asks for
 * a click rather than unsubscribing on load, since mail scanners open links too. */
export function UnsubscribePage() {
  const { token = '' } = useParams()
  const [params] = useSearchParams()
  const kind = emailKind(params.get('kind'))
  const settings = useEmailSettingsByLink(token)
  const unsubscribe = useUnsubscribe(token)

  if (settings.isPending) {
    return <LoadingNote>Loading your email settings…</LoadingNote>
  }

  const settingsLink = (
    <Anchor component={Link} to="/profile">
      your profile
    </Anchor>
  )
  if (settings.isError) {
    return (
      <Stack maw={520}>
        <Title order={2}>Email settings</Title>
        <ErrorNote error={settings.error} />
        <Text size="sm" c="dimmed" ta="center">
          You can also choose which emails you get on {settingsLink}.
        </Text>
      </Stack>
    )
  }

  const off = new Set(settings.data.email_opt_outs)
  const allOff = EMAIL_KINDS.every((k) => off.has(k.kind))
  const kindOff = kind ? off.has(kind.kind) : allOff
  return (
    <Stack maw={520}>
      <Title order={2}>Email settings</Title>
      {kindOff ? (
        <Alert color="green">
          {allOff
            ? "You won't get any more emails from Board Game Group."
            : `You won't get any more emails about ${kind?.about}.`}{' '}
          You can turn them back on from {settingsLink}.
        </Alert>
      ) : (
        <>
          <Text>
            {kind
              ? `Stop getting emails about ${kind.about}?`
              : 'Stop getting emails from Board Game Group?'}
          </Text>
          <Group>
            <Button
              loading={unsubscribe.isPending && unsubscribe.variables !== null}
              onClick={() => unsubscribe.mutate(kind?.kind ?? null)}
            >
              {kind ? 'Stop these emails' : 'Stop all emails'}
            </Button>
            {kind && (
              <Button
                variant="default"
                loading={unsubscribe.isPending && unsubscribe.variables === null}
                onClick={() => unsubscribe.mutate(null)}
              >
                Stop all emails
              </Button>
            )}
          </Group>
        </>
      )}
      {kindOff && kind && !allOff && (
        <Group>
          <Button
            variant="default"
            loading={unsubscribe.isPending}
            onClick={() => unsubscribe.mutate(null)}
          >
            Stop all emails too
          </Button>
        </Group>
      )}
      {unsubscribe.isError && <Alert color="red">{unsubscribe.error.message}</Alert>}
    </Stack>
  )
}
