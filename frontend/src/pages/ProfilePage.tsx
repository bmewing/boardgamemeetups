import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import {
  Alert,
  Button,
  Center,
  Divider,
  Group,
  Input,
  Loader,
  Modal,
  SegmentedControl,
  Select,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { useMemo } from 'react'

import type { UserProfile } from '../api/client'
import { useDeleteMe, useMe, useUpdateMe } from '../api/me'

const VISIBILITY_OPTIONS = [
  { value: 'private', label: 'Only me' },
  { value: 'friends', label: 'Friends' },
  { value: 'public', label: 'Everyone' },
]

const browserTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone

function timeZoneOptions(current: string) {
  return Array.from(new Set([current, browserTimeZone, ...Intl.supportedValuesOf('timeZone')]))
}

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
  const zones = useMemo(() => timeZoneOptions(profile.time_zone), [profile.time_zone])

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
        <TextInput label="Display name" maxLength={80} {...form.getInputProps('display_name')} />
        <Select
          label="Time zone"
          data={zones}
          searchable
          allowDeselect={false}
          description={
            form.values.time_zone !== browserTimeZone ? (
              <>
                Your browser is set to {browserTimeZone}.{' '}
                <Button
                  variant="transparent"
                  size="compact-xs"
                  p={0}
                  onClick={() => form.setFieldValue('time_zone', browserTimeZone)}
                >
                  Use it
                </Button>
              </>
            ) : undefined
          }
          {...form.getInputProps('time_zone')}
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
    return (
      <Center py="xl">
        <Loader />
      </Center>
    )
  }
  if (me.isError) return <Alert color="red">{me.error.message}</Alert>

  return (
    <Stack maw={520}>
      <Title order={2}>Profile</Title>
      <Text size="sm" c="dimmed">
        Signed in as {me.data.email ?? 'unknown email'}
      </Text>
      <ProfileForm profile={me.data} />
      <Divider my="md" />
      <DeleteAccount />
    </Stack>
  )
}
