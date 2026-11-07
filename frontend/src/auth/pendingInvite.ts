import { useKindeAuth } from '@kinde-oss/kinde-auth-react'
import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router'

// Signing in through Kinde always comes back to the home page, so a link opened while
// signed out (a friend invite, or the Discord bot's link) is remembered for this tab and
// picked up again once they're back.
const INVITE = { key: 'pendingInvite', path: '/invite/' }
const DISCORD = { key: 'pendingDiscordLink', path: '/discord/link/' }

function storage(): Storage | null {
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

function remember(key: string, token: string) {
  try {
    storage()?.setItem(key, token)
  } catch {
    // Without storage they'll just need to open the link again after signing in.
  }
}

function forget(key: string) {
  try {
    storage()?.removeItem(key)
  } catch {
    // Nothing to forget.
  }
}

function pending(key: string): string | null {
  try {
    return storage()?.getItem(key) ?? null
  } catch {
    return null
  }
}

export const rememberInvite = (token: string) => remember(INVITE.key, token)
export const forgetInvite = () => forget(INVITE.key)
export const rememberDiscordLink = (token: string) => remember(DISCORD.key, token)
export const forgetDiscordLink = () => forget(DISCORD.key)

/** Once signed in, go back to a link that sent them off to sign in. */
export function useResumeInvite() {
  const { isAuthenticated } = useKindeAuth()
  const navigate = useNavigate()
  const { pathname } = useLocation()

  useEffect(() => {
    if (!isAuthenticated) return
    for (const { key, path } of [INVITE, DISCORD]) {
      if (pathname.startsWith(path)) return
      const token = pending(key)
      if (token) {
        navigate(`${path}${encodeURIComponent(token)}`, { replace: true })
        return
      }
    }
  }, [isAuthenticated, pathname, navigate])
}
