import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import { detailOf } from './collection'
import { groupKey } from './groups'
import type { components } from './schema'

export type RpgSystemSummary = components['schemas']['RpgSystemSummary']
export type RpgSystemDetail = components['schemas']['RpgSystemDetail']
export type CustomSystemIn = components['schemas']['CustomSystemIn']
export type MySystem = components['schemas']['MySystemRead']
export type MySystemUpdate = components['schemas']['MySystemUpdate']
export type SystemAnswers = components['schemas']['SystemAnswers']
export type Character = components['schemas']['CharacterRead']
export type CharacterCreate = components['schemas']['CharacterCreate']
export type CharacterUpdate = components['schemas']['CharacterUpdate']
export type CharacterStatus = components['schemas']['CharacterStatus']
export type Party = components['schemas']['PartyRead']

export const MY_SYSTEMS_KEY = ['me', 'rpg-systems'] as const
export const MY_CHARACTERS_KEY = ['me', 'characters'] as const
const systemKey = (id: number) => ['rpg-systems', id] as const
const characterKey = (id: string) => ['characters', id] as const
const partyKey = (groupId: string) => [...groupKey(groupId), 'party'] as const

export const STATUS_LABELS: Record<CharacterStatus, string> = {
  active: 'Active',
  retired: 'Retired',
  dead: 'Dead',
}

export function useRpgSystemSearch(query: string) {
  const q = query.trim()
  return useQuery({
    queryKey: ['rpg-systems', 'search', q],
    enabled: q.length >= 2,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/rpg-systems/search', {
        params: { query: { q } },
      })
      if (error) throw new Error('Search failed')
      return data
    },
  })
}

export function useRpgSystem(systemId: number) {
  return useQuery({
    queryKey: systemKey(systemId),
    enabled: Number.isInteger(systemId),
    queryFn: async () => {
      const { data, error, response } = await api.GET('/api/rpg-systems/{system_id}', {
        params: { path: { system_id: systemId } },
      })
      if (response.status === 404) throw new Error('No such system')
      if (error) throw new Error('Could not load this system')
      return data
    },
  })
}

/** Add a system that isn't on RPGGeek. It lands in your systems as one you know. */
export function useAddCustomSystem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: CustomSystemIn) => {
      const { data, error } = await api.POST('/api/rpg-systems', { body })
      if (error) throw new Error(detailOf(error, 'Could not add this system'))
      return data
    },
    onSuccess: (system) => {
      queryClient.setQueryData(systemKey(system.id), system)
      return queryClient.invalidateQueries({ queryKey: MY_SYSTEMS_KEY })
    },
  })
}

export function useUpdateCustomSystem(systemId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: CustomSystemIn) => {
      const { data, error } = await api.PUT('/api/rpg-systems/{system_id}', {
        params: { path: { system_id: systemId } },
        body,
      })
      if (error) throw new Error(detailOf(error, 'Could not save this system'))
      return data
    },
    onSuccess: (system) => {
      queryClient.setQueryData(systemKey(system.id), system)
      return queryClient.invalidateQueries({ queryKey: MY_SYSTEMS_KEY })
    },
  })
}

export function useMySystems() {
  return useQuery({
    queryKey: MY_SYSTEMS_KEY,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/me/rpg-systems')
      if (error) throw new Error('Could not load your systems')
      return data
    },
  })
}

/** Saves go out one at a time, in order, so quick taps can't land out of order. */
export function useUpdateMySystem() {
  const queryClient = useQueryClient()
  return useMutation({
    scope: { id: 'my-systems' },
    mutationFn: async ({ systemId, changes }: { systemId: number; changes: MySystemUpdate }) => {
      const { data, error } = await api.PUT('/api/me/rpg-systems/{system_id}', {
        params: { path: { system_id: systemId } },
        body: changes,
      })
      if (error) throw new Error(detailOf(error, 'Could not save that'))
      return data
    },
    onSuccess: (saved) => {
      queryClient.setQueryData<MySystem[]>(MY_SYSTEMS_KEY, (list) => {
        if (!list) return list
        const others = list.filter((m) => m.system.id !== saved.system.id)
        return [...others, saved].sort((a, b) => a.system.name.localeCompare(b.system.name))
      })
      // Groups show what members say about their system.
      return queryClient.invalidateQueries({ queryKey: ['groups'] })
    },
  })
}

export function useRemoveMySystem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (systemId: number) => {
      const { error } = await api.DELETE('/api/me/rpg-systems/{system_id}', {
        params: { path: { system_id: systemId } },
      })
      if (error) throw new Error('Could not remove this system')
    },
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: MY_SYSTEMS_KEY }),
        queryClient.invalidateQueries({ queryKey: ['groups'] }),
      ]),
  })
}

export function useMyCharacters() {
  return useQuery({
    queryKey: MY_CHARACTERS_KEY,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/me/characters')
      if (error) throw new Error('Could not load your characters')
      return data
    },
  })
}

/** Null when there's no such character, or it isn't yours or in one of your groups. */
export function useCharacter(characterId: string) {
  return useQuery({
    queryKey: characterKey(characterId),
    queryFn: async () => {
      const { data, error, response } = await api.GET('/api/characters/{character_id}', {
        params: { path: { character_id: characterId } },
      })
      if (response.status === 404 || response.status === 422) return null
      if (error) throw new Error('Could not load this character')
      return data
    },
  })
}

function useCharacterSaved() {
  const queryClient = useQueryClient()
  return (character: Character, groupIds: (string | undefined)[] = []) => {
    queryClient.setQueryData(characterKey(character.id), character)
    const groups = new Set([character.group?.id, ...groupIds].filter(Boolean) as string[])
    return Promise.all([
      queryClient.invalidateQueries({ queryKey: MY_CHARACTERS_KEY }),
      ...[...groups].map((id) => queryClient.invalidateQueries({ queryKey: partyKey(id) })),
    ])
  }
}

export function useCreateCharacter() {
  const saved = useCharacterSaved()
  return useMutation({
    mutationFn: async (body: CharacterCreate) => {
      const { data, error } = await api.POST('/api/me/characters', { body })
      if (error) throw new Error(detailOf(error, 'Could not make this character'))
      return data
    },
    onSuccess: (character) => saved(character),
  })
}

export function useUpdateCharacter(characterId: string, previousGroupId?: string) {
  const saved = useCharacterSaved()
  return useMutation({
    mutationFn: async (body: CharacterUpdate) => {
      const { data, error } = await api.PATCH('/api/characters/{character_id}', {
        params: { path: { character_id: characterId } },
        body,
      })
      if (error) throw new Error(detailOf(error, 'Could not save this character'))
      return data
    },
    // The party it left needs refreshing too.
    onSuccess: (character) => saved(character, [previousGroupId]),
  })
}

/** Move any of your characters into a party (or out, with a null group). */
export function useMoveCharacter() {
  const saved = useCharacterSaved()
  return useMutation({
    mutationFn: async ({
      character,
      groupId,
    }: {
      character: Character
      groupId: string | null
    }) => {
      const { data, error } = await api.PATCH('/api/characters/{character_id}', {
        params: { path: { character_id: character.id } },
        body: { group_id: groupId },
      })
      if (error) throw new Error(detailOf(error, 'Could not move this character'))
      return data
    },
    onSuccess: (moved, { character }) => saved(moved, [character.group?.id]),
  })
}

export function useDeleteCharacter(characterId: string, groupId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { error } = await api.DELETE('/api/characters/{character_id}', {
        params: { path: { character_id: characterId } },
      })
      if (error) throw new Error(detailOf(error, 'Could not delete this character'))
    },
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: characterKey(characterId) })
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: MY_CHARACTERS_KEY }),
        groupId ? queryClient.invalidateQueries({ queryKey: partyKey(groupId) }) : undefined,
      ])
    },
  })
}

export function useParty(groupId: string, enabled = true) {
  return useQuery({
    queryKey: partyKey(groupId),
    enabled,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/groups/{group_id}/party', {
        params: { path: { group_id: groupId } },
      })
      if (error) throw new Error("Could not load the group's party")
      return data
    },
  })
}
