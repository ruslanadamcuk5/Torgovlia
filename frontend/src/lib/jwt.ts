export interface JwtClaims {
  sub?: string
  role?: string
  scope?: string
  imp?: boolean
  imp_by?: number
  imp_reason?: string
  exp?: number
  iat?: number
}

function base64UrlDecode(value: string): string {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/')
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
  return decodeURIComponent(
    Array.from(atob(padded))
      .map((char) => `%${char.charCodeAt(0).toString(16).padStart(2, '0')}`)
      .join(''),
  )
}

export function decodeClaims(token: string | null): JwtClaims | null {
  if (!token) return null
  const parts = token.split('.')
  if (parts.length < 2) return null
  try {
    return JSON.parse(base64UrlDecode(parts[1])) as JwtClaims
  } catch {
    return null
  }
}

export function impersonationFromToken(token: string | null): JwtClaims | null {
  const claims = decodeClaims(token)
  if (!claims?.imp) return null
  return claims
}
