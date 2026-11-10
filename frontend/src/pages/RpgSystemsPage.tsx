import { Anchor, Loader, Modal, Stack, Text, TextInput, Title } from '@mantine/core'
import { useDebouncedValue, useDisclosure } from '@mantine/hooks'
import { useNavigate, useSearchParams } from 'react-router'

import { useAddCustomSystem, useMySystems, useRpgSystemSearch } from '../api/rpg'
import { ErrorNote, MascotNote } from '../components/mascot/MascotNote'
import { MySystemAnswers } from '../components/rpg/MySystemAnswers'
import { RpgSystemForm } from '../components/rpg/RpgSystemForm'
import { SystemCard } from '../components/rpg/SystemCard'

/** For a system RPGGeek doesn't list: a homebrew, or one it just doesn't have. */
function AddCustomSystem({ name }: { name: string }) {
  const [opened, { open, close }] = useDisclosure(false)
  const add = useAddCustomSystem()
  const navigate = useNavigate()
  return (
    <>
      <Text size="sm" c="dimmed">
        Not on RPGGeek? A homebrew, or a system it just doesn't list?{' '}
        <Anchor component="button" type="button" size="sm" onClick={open}>
          Add it yourself
        </Anchor>
      </Text>
      <Modal opened={opened} onClose={close} title="Add a system that isn't on RPGGeek">
        <Stack>
          <Text size="sm" c="dimmed">
            It goes in your systems as one you know. People find it through you: your groups and
            characters that use it.
          </Text>
          <RpgSystemForm
            initial={{ name }}
            submitLabel="Add system"
            busy={add.isPending}
            error={add.error?.message}
            onCancel={close}
            onSubmit={(system) =>
              add.mutate(system, { onSuccess: (added) => navigate(`/rpg-systems/${added.id}`) })
            }
          />
        </Stack>
      </Modal>
    </>
  )
}

export function RpgSystemsPage() {
  // Keep the query in the URL so back-navigation returns to the same results.
  const [params, setParams] = useSearchParams()
  const query = params.get('q') ?? ''
  const [debounced] = useDebouncedValue(query, 300)
  const search = useRpgSystemSearch(debounced)
  const mySystems = useMySystems()
  const mine = new Map((mySystems.data ?? []).map((m) => [m.system.id, m]))

  return (
    <Stack>
      <Title order={2}>RPG systems</Title>
      <TextInput
        label="Search RPGGeek"
        description="A system we haven't seen yet can take a few seconds to find."
        placeholder="e.g. Blades in the Dark"
        value={query}
        onChange={(event) =>
          setParams(event.currentTarget.value ? { q: event.currentTarget.value } : {}, {
            replace: true,
          })
        }
        rightSection={search.isFetching ? <Loader size="xs" /> : null}
        autoFocus
      />
      {search.isError && <ErrorNote error={search.error} onRetry={search.refetch} />}
      {!query.trim() && (
        <MascotNote pose="think" title="What do you play?">
          <Text c="dimmed" maw={420}>
            Search for a system to say you know it, can GM it, or want to play it. Your RPG groups
            see your answers.
          </Text>
        </MascotNote>
      )}
      {search.data?.length === 0 && !search.isFetching && (
        <MascotNote pose="think">
          <Text c="dimmed">No systems found for “{debounced.trim()}”.</Text>
        </MascotNote>
      )}
      <Stack gap="xs">
        {search.data?.map((system) => (
          <SystemCard
            key={system.id}
            system={system}
            below={<MySystemAnswers systemId={system.id} row={mine.get(system.id)} />}
          />
        ))}
      </Stack>
      <AddCustomSystem name={debounced.trim()} />
    </Stack>
  )
}
