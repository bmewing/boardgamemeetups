import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import {
  Alert,
  Button,
  Divider,
  Group,
  Input,
  Modal,
  SegmentedControl,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'

import type { UserProfile } from '../api/client'
import { useUnlinkDiscord } from '../api/discord'
import { EMAIL_KINDS } from '../api/email'
import { useDeleteMe, useMe, useUpdateMe } from '../api/me'
import { AchievementList } from '../components/achievements/AchievementList'
import { PiecePicker } from '../components/pieces/PiecePicker'
import { TimeZoneSelect } from '../components/TimeZoneSelect'
import { ErrorNote, LoadingNote } from '../components/mascot/MascotNote'

const VISIBILITY_OPTIONS = [
  { value: 'private', label: 'Only me' },
  { value: 'friends', label: 'Friends' },
  { value: 'public', label: 'Everyone' },
]

type ProfileFormValues = Pick<
  UserProfile,
  'display_name' | 'time_zone' | 'collection_visibility'
> & { bgg_username: string }

function toFormValues(profile: UserProfile): ProfileFormValues {
  return {
    display_name: profile.display_name,
    time_zone: profile.time_zone,
    bgg_username: profile.bgg_username ?? '',
    collection_visibility: profile.collection_visibility,
  }
}

function ProfileForm({ profile }: { profile: UserProfile }) {
  const update = useUpdateMe()
  const form = useForm<ProfileFormValues>({
    initialValues: toFormValues(profile),
    validate: {
      display_name: (value) => (value.trim() ? null : 'Enter a display name'),
    },
  })

  const save = (values: ProfileFormValues) =>
    update.mutate(values, {
      // Show what the server stored (e.g. trimmed names) and mark the form clean.
      onSuccess: (saved) => {
        form.setInitialValues(toFormValues(saved))
        form.setValues(toFormValues(saved))
      },
    })

  return (
    <form onSubmit={form.onSubmit(save)}>
      <Stack>
        <TextInput
          label="Display name"
          description="Your username: friends find you by it, so no one else can have it."
          maxLength={80}
          {...form.getInputProps('display_name')}
        />
        <TimeZoneSelect
          value={form.values.time_zone}
          onChange={(zone) => form.setFieldValue('time_zone', zone)}
          description="New groups you make start in this time zone."
          error={form.errors.time_zone}
        />
        <TextInput
          label="BoardGameGeek username"
          description="Optional. Used later to import your collection."
          maxLength={64}
          {...form.getInputProps('bgg_username')}
        />
        <Input.Wrapper
          label="Who can see your collection"
          description="Meetup recommendations always use the collections of people attending."
        >
          <SegmentedControl
            mt={4}
            fullWidth
            data={VISIBILITY_OPTIONS}
            {...form.getInputProps('collection_visibility')}
          />
        </Input.Wrapper>
        {update.isError && <Alert color="red">{update.error.message}</Alert>}
        <Group>
          <Button type="submit" loading={update.isPending} disabled={!form.isDirty()}>
            Save
          </Button>
          {update.isSuccess && !form.isDirty() && (
            <Text size="sm" c="dimmed">
              Saved
            </Text>
          )}
        </Group>
      </Stack>
    </form>
  )
}

/** One switch per kind of email; each change saves straight away. */
function EmailSettings({ profile }: { profile: UserProfile }) {
  const update = useUpdateMe()
  const off = new Set(profile.email_opt_outs)

  return (
    <Stack gap="sm">
      <Title order={4}>Emails</Title>
      <Text size="sm" c="dimmed">
        Sent to {profile.email ?? 'your email'}. Every email also has a link to stop that kind.
      </Text>
      {EMAIL_KINDS.map(({ kind, label, description }) => (
        <Switch
          key={kind}
          label={label}
          description={description}
          checked={!off.has(kind)}
          disabled={update.isPending}
          onChange={(event) => {
            const next = new Set(off)
            if (event.currentTarget.checked) next.delete(kind)
            else next.add(kind)
            update.mutate({ email_opt_outs: [...next] })
          }}
        />
      ))}
      {update.isError && <Alert color="red">{update.error.message}</Alert>}
    </Stack>
  )
}

function DiscordSettings({ profile }: { profile: UserProfile }) {
  const unlink = useUnlinkDiscord()

  return (
    <Stack gap="xs">
      <Title order={4}>Discord</Title>
      {profile.discord_username ? (
        <>
          <Text size="sm" c="dimmed">
            Linked to @{profile.discord_username}. The bot's buttons in Discord answer for you.
          </Text>
          <Group>
            <Button variant="default" loading={unlink.isPending} onClick={() => unlink.mutate()}>
              Unlink Discord
            </Button>
          </Group>
        </>
      ) : (
        <Text size="sm" c="dimmed">
          Not linked. In a Discord server with the Board Game Group bot, type{' '}
          <code>/bggroup link</code>.
        </Text>
      )}
      {unlink.isError && <Alert color="red">{unlink.error.message}</Alert>}
    </Stack>
  )
}

function DeleteAccount() {
  const { logout } = useKindeAuth()
  const remove = useDeleteMe()
  const [opened, { open, close }] = useDisclosure(false)

  return (
    <Stack gap="xs">
      <Title order={4}>Delete account</Title>
      <Text size="sm" c="dimmed">
        Removes your profile, collection, ratings and meetup history from this app.
      </Text>
      <Group>
        <Button color="red" variant="outline" onClick={open}>
          Delete my account
        </Button>
      </Group>
      <Modal opened={opened} onClose={close} title="Delete your account?">
        <Stack>
          <Text size="sm">This can't be undone.</Text>
          {remove.isError && <Alert color="red">{remove.error.message}</Alert>}
          <Group justify="flex-end">
            <Button variant="default" onClick={close}>
              Cancel
            </Button>
            <Button
              color="red"
              loading={remove.isPending}
              onClick={() => remove.mutate(undefined, { onSuccess: () => logout() })}
            >
              Delete
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  )
}

export function ProfilePage() {
  const me = useMe()

  if (me.isPending) {
    return <LoadingNote>Loading your profile…</LoadingNote>
  }
  if (me.isError) return <ErrorNote error={me.error} onRetry={me.refetch} />

  return (
    <Stack maw={520}>
      <Title order={2}>Profile</Title>
      <Text size="sm" c="dimmed">
        Signed in as {me.data.email ?? 'unknown email'}
      </Text>
      <ProfileForm profile={me.data} />
      <Divider my="md" />
      <PiecePicker profile={me.data} />
      <Divider my="md" />
      <AchievementList profile={me.data} />
      <Divider my="md" />
      <EmailSettings profile={me.data} />
      <Divider my="md" />
      <DiscordSettings profile={me.data} />
      <Divider my="md" />
      <DeleteAccount />
    </Stack>
  )
}
