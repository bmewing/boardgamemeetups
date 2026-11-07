import {
  Avatar,
  Badge,
  Button,
  Combobox,
  Group,
  Loader,
  Text,
  TextInput,
  useCombobox,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { type FormEvent, useState } from 'react'

import { type Person, type PersonMatch, type PersonPick, usePeopleSearch } from '../api/friends'

const RELATION_LABELS: Partial<Record<PersonMatch['relation'], string>> = {
  friends: 'Friend',
  incoming: 'Asked you',
  outgoing: 'Asked',
}

/**
 * A box that suggests people as you type their username, and also takes a full email
 * address. `onPick` gets whoever was picked from the list, or the email typed in.
 * `unavailable` names people to show but not pick (say, already in the group).
 * `suggestions` are offered before anything is typed (narrowed by the first letter or so),
 * such as your friends who aren't in the group yet.
 */
export function PersonPicker({
  label,
  description,
  actionLabel,
  busy = false,
  unavailable = {},
  suggestions = [],
  onPick,
  onTyping,
}: {
  label: string
  description?: string
  actionLabel: string
  busy?: boolean
  unavailable?: Record<string, string>
  suggestions?: Person[]
  onPick: (pick: PersonPick, person: Person | null) => void
  onTyping?: () => void
}) {
  const combobox = useCombobox({ onDropdownClose: () => combobox.resetSelectedOption() })
  const [text, setText] = useState('')
  const [chosen, setChosen] = useState<Person | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [query] = useDebouncedValue(text, 200)
  const searching = query.trim().length >= 2
  const search = usePeopleSearch(chosen ? '' : query)
  const typed = text.trim().toLowerCase()
  const suggested: PersonMatch[] = suggestions
    .filter((p) => p.display_name.toLowerCase().includes(typed))
    .map((person) => ({ person, relation: 'friends' }))
  const matches = searching ? (search.data ?? []) : suggested

  const choose = (person: Person) => {
    setChosen(person)
    setText(person.display_name)
    setProblem(null)
    combobox.closeDropdown()
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const typed = text.trim()
    const exact = matches.find(
      (m) =>
        m.person.display_name.toLowerCase() === typed.toLowerCase() && !unavailable[m.person.id],
    )
    const person = chosen ?? exact?.person ?? null
    if (person) {
      onPick({ user_id: person.id }, person)
    } else if (typed.includes('@')) {
      onPick({ email: typed }, null)
    } else {
      setProblem('Pick someone from the suggestions, or type their full email address.')
      return
    }
    setText('')
    setChosen(null)
  }

  const options = matches.map(({ person, relation }) => {
    const reason = unavailable[person.id]
    const tag = reason ?? RELATION_LABELS[relation]
    return (
      <Combobox.Option value={person.id} key={person.id} disabled={Boolean(reason)}>
        <Group gap="sm" wrap="nowrap">
          <Avatar
            src={person.avatar_url}
            name={person.display_name}
            color="initials"
            radius="xl"
            size="sm"
          />
          <Text size="sm" style={{ flex: 1 }}>
            {person.display_name}
          </Text>
          {tag && (
            <Badge size="xs" variant="light" color={reason ? 'gray' : undefined}>
              {tag}
            </Badge>
          )}
        </Group>
      </Combobox.Option>
    )
  })

  const showDropdown = !chosen && (searching || suggested.length > 0)
  return (
    <form onSubmit={submit}>
      <Group align="flex-end" gap="xs" wrap="nowrap">
        <Combobox
          store={combobox}
          withinPortal
          onOptionSubmit={(id) => {
            const match = matches.find((m) => m.person.id === id)
            if (match) choose(match.person)
          }}
        >
          <Combobox.Target>
            <TextInput
              label={label}
              description={description}
              placeholder="Username or email"
              value={text}
              error={Boolean(problem)}
              autoComplete="off"
              style={{ flex: 1 }}
              rightSection={search.isFetching ? <Loader size="xs" /> : null}
              onChange={(e) => {
                setText(e.currentTarget.value)
                setChosen(null)
                setProblem(null)
                onTyping?.()
                combobox.openDropdown()
                combobox.updateSelectedOptionIndex()
              }}
              onFocus={() => combobox.openDropdown()}
              onBlur={() => combobox.closeDropdown()}
            />
          </Combobox.Target>
          <Combobox.Dropdown hidden={!showDropdown}>
            <Combobox.Options mah={280} style={{ overflowY: 'auto' }}>
              {options.length > 0 ? (
                options
              ) : (
                <Combobox.Empty>
                  {search.isFetching
                    ? 'Searching…'
                    : text.includes('@')
                      ? 'No one with that email yet'
                      : 'No one by that name'}
                </Combobox.Empty>
              )}
            </Combobox.Options>
          </Combobox.Dropdown>
        </Combobox>
        <Button type="submit" loading={busy}>
          {actionLabel}
        </Button>
      </Group>
      {problem && (
        <Text size="xs" c="red" mt={4}>
          {problem}
        </Text>
      )}
    </form>
  )
}
