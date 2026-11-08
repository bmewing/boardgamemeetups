import { MutationCache, QueryClient } from '@tanstack/react-query'

import { ME_KEY } from './me'

/**
 * The app's query client. Almost anything you do can earn an achievement, and the profile
 * (`/api/me`) carries them, so it's refreshed after every change you make. Changes to the
 * profile itself (mutation key ME_KEY) already return it.
 */
export function createQueryClient() {
  const client: QueryClient = new QueryClient({
    mutationCache: new MutationCache({
      onSuccess: (_data, _variables, _context, mutation) => {
        if (mutation.options.mutationKey?.[0] !== ME_KEY[0]) {
          void client.invalidateQueries({ queryKey: ME_KEY })
        }
      },
    }),
  })
  return client
}
