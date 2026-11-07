import { createBrowserRouter } from 'react-router'

import { RequireAuth } from './auth/RequireAuth'
import { Layout } from './components/Layout'
import { AdminPage } from './pages/AdminPage'
import { BggPullPage } from './pages/BggPullPage'
import { CollectionPage } from './pages/CollectionPage'
import { DiscordLinkPage } from './pages/DiscordLinkPage'
import { FileImportPage } from './pages/FileImportPage'
import { FriendsPage } from './pages/FriendsPage'
import { GamePage } from './pages/GamePage'
import { GamesPage } from './pages/GamesPage'
import { GroupPage } from './pages/GroupPage'
import { GroupsPage } from './pages/GroupsPage'
import { HomePage } from './pages/HomePage'
import { InvitePage } from './pages/InvitePage'
import { PrivacyPage, TermsPage } from './pages/LegalPages'
import { MeetupPage } from './pages/MeetupPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PersonPage } from './pages/PersonPage'
import { ProfilePage } from './pages/ProfilePage'
import { UnsubscribePage } from './pages/UnsubscribePage'

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
        path: 'admin',
        element: (
          <RequireAuth>
            <AdminPage />
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
      {
        path: 'groups',
        element: (
          <RequireAuth>
            <GroupsPage />
          </RequireAuth>
        ),
      },
      {
        path: 'groups/:groupId',
        element: (
          <RequireAuth>
            <GroupPage />
          </RequireAuth>
        ),
      },
      {
        path: 'meetups/:meetupId',
        element: (
          <RequireAuth>
            <MeetupPage />
          </RequireAuth>
        ),
      },
      // Open to anyone with the link: it says who sent it before they sign up.
      { path: 'invite/:token', element: <InvitePage /> },
      // From the Discord bot: says which Discord account before asking them to sign in.
      { path: 'discord/link/:token', element: <DiscordLinkPage /> },
      // Open to anyone: sign-in providers link to these.
      { path: 'terms', element: <TermsPage /> },
      { path: 'privacy', element: <PrivacyPage /> },
      // From a link in an email: works without signing in.
      { path: 'unsubscribe/:token', element: <UnsubscribePage /> },
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
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
