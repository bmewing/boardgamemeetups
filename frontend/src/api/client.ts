import createClient from 'openapi-fetch'

import type { paths } from './schema'

// Typed client generated from the FastAPI OpenAPI schema (`npm run gen:api`).
export const api = createClient<paths>({ baseUrl: window.location.origin })
