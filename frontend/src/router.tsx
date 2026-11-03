import { createBrowserRouter } from 'react-router'

import { RequireAuth } from './auth/RequireAuth'
import { Layout } from './components/Layout'
import { HomePage } from './pages/HomePage'
import { ProfilePage } from './pages/ProfilePage'

export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { index: true, element: <HomePage /> },
      {
        path: 'profile',
        element: (
          <RequireAuth>
            <ProfilePage />
          </RequireAuth>
        ),
      },
    ],
  },
])
