/** "2–4" for a run, "2, 4" when BGA skips counts. */
export function bgaCounts(counts: number[]) {
  const sorted = [...counts].sort((a, b) => a - b)
  const first = sorted[0]
  const last = sorted[sorted.length - 1]
  if (first === undefined || last === undefined) return ''
  if (first === last) return String(first)
  return sorted.length === last - first + 1 ? `${first}–${last}` : sorted.join(', ')
}
