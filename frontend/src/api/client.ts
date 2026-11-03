import createClient from 'openapi-fetch'

import type { components, paths } from './schema'

export type UserProfile = components['schemas']['UserRead']
export type UserProfileUpdate = components['schemas']['UserUpdate']

type TokenGetter = () => Promise<string | undefined>

let getAccessToken: TokenGetter = async () => undefined

/** Called by the auth provider so API requests carry the signed-in user's token. */
export function setAccessTokenGetter(getter: TokenGetter) {
  getAccessToken = getter
}

// Typed client generated from the FastAPI OpenAPI schema (`npm run gen:api`).
export const api = createClient<paths>({ baseUrl: window.location.origin })

api.use({
  async onRequest({ request }) {
    const token = await getAccessToken()
    if (token) request.headers.set('Authorization', `Bearer ${token}`)
    return request
  },
})
