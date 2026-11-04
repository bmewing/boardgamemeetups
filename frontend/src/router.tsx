import { createBrowserRouter } from 'react-router'

import { RequireAuth } from './auth/RequireAuth'
import { Layout } from './components/Layout'
import { BggPullPage } from './pages/BggPullPage'
import { CollectionPage } from './pages/CollectionPage'
import { FileImportPage } from './pages/FileImportPage'
import { FriendsPage } from './pages/FriendsPage'
import { GamePage } from './pages/GamePage'
import { GamesPage } from './pages/GamesPage'
import { HomePage } from './pages/HomePage'
import { InvitePage } from './pages/InvitePage'
import { PersonPage } from './pages/PersonPage'
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
        path: 'collection',
        element: (
          <RequireAuth>
            <CollectionPage />
          </RequireAuth>
        ),
      },
      {
        path: 'collection/pull',
        element: (
          <RequireAuth>
            <BggPullPage />
          </RequireAuth>
        ),
      },
      {
        path: 'collection/import',
        element: (
          <RequireAuth>
            <FileImportPage />
          </RequireAuth>
        ),
      },
      {
        path: 'friends',
        element: (
          <RequireAuth>
            <FriendsPage />
          </RequireAuth>
        ),
      },
      {
        path: 'people/:userId',
        element: (
          <RequireAuth>
            <PersonPage />
          </RequireAuth>
        ),
      },
      // Open to anyone with the link: it says who sent it before they sign up.
      { path: 'invite/:token', element: <InvitePage /> },
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
