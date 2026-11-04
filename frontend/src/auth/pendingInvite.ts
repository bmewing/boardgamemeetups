import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router'

// Signing in through Kinde always comes back to the home page, so an invite opened while
// signed out is remembered for this tab and picked up again once they're back.
const KEY = 'pendingInvite'

function storage(): Storage | null {
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

export function rememberInvite(token: string) {
  try {
    storage()?.setItem(KEY, token)
  } catch {
    // Without storage they'll just need to open the link again after signing in.
  }
}

export function forgetInvite() {
  try {
    storage()?.removeItem(KEY)
  } catch {
    // Nothing to forget.
  }
}

function pendingInvite(): string | null {
  try {
    return storage()?.getItem(KEY) ?? null
  } catch {
    return null
  }
}

/** Once signed in, go back to an invite that sent them off to sign in. */
export function useResumeInvite() {
  const { isAuthenticated } = useKindeAuth()
  const navigate = useNavigate()
  const { pathname } = useLocation()

  useEffect(() => {
    if (!isAuthenticated || pathname.startsWith('/invite/')) return
    const token = pendingInvite()
    if (token) navigate(`/invite/${encodeURIComponent(token)}`, { replace: true })
  }, [isAuthenticated, pathname, navigate])
}
