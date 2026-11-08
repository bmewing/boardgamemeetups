import '@mantine/core/styles.css'
import '@fontsource-variable/fredoka'
import '@fontsource-variable/nunito'
import './styles/global.css'

import { MantineProvider } from '@mantine/core'
import { QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router'

import { createQueryClient } from './api/queryClient'
import { AuthProvider } from './auth/AuthProvider'
import { router } from './router'
import { cssVariablesResolver, theme } from './theme'

const queryClient = createQueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MantineProvider
      theme={theme}
      cssVariablesResolver={cssVariablesResolver}
      defaultColorScheme="auto"
    >
      <AuthProvider>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </AuthProvider>
    </MantineProvider>
  </StrictMode>,
)
