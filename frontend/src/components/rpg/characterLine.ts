import type { Character } from '../../api/rpg'

/** "Level 3 Elf Wizard": whichever of those the player filled in. */
export function characterLine(character: Character): string {
  const level = character.level != null ? `Level ${character.level}` : null
  return [level, character.ancestry, character.class_role].filter(Boolean).join(' ')
}
