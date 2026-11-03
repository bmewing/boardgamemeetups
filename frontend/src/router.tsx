import { createBrowserRouter } from 'react-router'

import { RequireAuth } from './auth/RequireAuth'
import { Layout } from './components/Layout'
import { GamePage } from './pages/GamePage'
import { GamesPage } from './pages/GamesPage'
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
      {
        path: 'games',
        element: (
          <RequireAuth>
            <GamesPage />
          </RequireAuth>
        ),
      },
      {
        path: 'games/:gameId',
        element: (
          <RequireAuth>
            <GamePage />
          </RequireAuth>
        ),
      },
    ],
  },
])
