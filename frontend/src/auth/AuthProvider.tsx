import { KindeProvider, useKindeAuth } from '@kinde-oss/kinde-auth-react'
import type { ReactNode } from 'react'

import { setAccessTokenGetter } from '../api/client'

export function TokenBridge({ children }: { children: ReactNode }) {
  const { getAccessToken } = useKindeAuth()
  // Set during render so it is in place before any child query fires.
  setAccessTokenGetter(getAccessToken)
  return children
}

export function AuthProvider({ children }: { children: ReactNode }) {
  return (
    <KindeProvider
      clientId={import.meta.env.VITE_KINDE_CLIENT_ID}
      domain={import.meta.env.VITE_KINDE_DOMAIN}
      audience={import.meta.env.VITE_KINDE_AUDIENCE}
      redirectUri={window.location.origin}
      logoutUri={window.location.origin}
      // Production signs in through Kinde on our own domain (auth.bggroup.app), where Kinde
      // keeps the refresh token in a secure httpOnly cookie. Local development uses the
      // kinde.com domain, which can't set that cookie, so there the refresh token goes in
      // localStorage instead (never in production).
      useInsecureForRefreshToken={import.meta.env.DEV}
    >
      <TokenBridge>{children}</TokenBridge>
    </KindeProvider>
  )
}
