/**
 * Where to go after an external step (like the payment page). The path travels in the URL, so
 * it is untrusted: only a path inside this app is accepted, never another site ("open redirect").
 */
export function safeInternalPath(candidate: string | null | undefined, fallback: string): string {
  if (!candidate) return fallback
  // Must start with a single "/", and carry no backslash, control characters or scheme.
  if (!candidate.startsWith('/') || candidate.startsWith('//') || candidate.includes('\\')) return fallback
  // eslint-disable-next-line no-control-regex
  if (/[\u0000-\u001f]/.test(candidate)) return fallback
  return candidate
}
