/** Stable hue for a compartment key (e.g. a vendor_id), so the same
 * vendor always renders the same color across a session. */
export function colorFor(key: string | null | undefined): string {
  if (!key) return '#4a5568'
  let hash = 0
  for (let i = 0; i < key.length; i++) {
    hash = (hash * 31 + key.charCodeAt(i)) >>> 0
  }
  const hue = hash % 360
  return `hsl(${hue}, 65%, 55%)`
}
