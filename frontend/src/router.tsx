import { createBrowserRouter } from 'react-router'

import { Layout } from './components/Layout'
import { HomePage } from './pages/HomePage'

export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [{ index: true, element: <HomePage /> }],
  },
])
