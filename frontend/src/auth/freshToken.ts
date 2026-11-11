/** A token this close to expiring is treated as expired, so it can't lapse mid-request. */
const MARGIN_SECONDS = 30

/** True if the token has expired or is about to. A token with no readable expiry is left alone. */
export function expiresSoon(token: string, nowMs = Date.now()): boolean {
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    const { exp } = JSON.parse(atob(payload)) as { exp?: unknown }
    return typeof exp === 'number' && exp - MARGIN_SECONDS <= nowMs / 1000
  } catch {
    return false
  }
}

type TokenGetter = () => Promise<string | undefined>

/**
 * Wraps the stored-token getter so an expired token is refreshed before it's sent.
 *
 * Kinde refreshes the access token on a timer, but phones pause timers while the browser is
 * in the background. Without this, the first requests after you come back to the app go out
 * with a dead token and fail. Requests that arrive together share one refresh.
 */
export function freshTokenGetter(getStoredToken: TokenGetter, refresh: () => Promise<unknown>) {
  let refreshing: Promise<unknown> | null = null
  return async () => {
    const token = await getStoredToken()
    if (!token || !expiresSoon(token)) return token
    refreshing ??= Promise.resolve()
      .then(refresh)
      .catch(() => undefined)
      .finally(() => {
        refreshing = null
      })
    await refreshing
    return getStoredToken()
  }
}
