import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router'
import { AuthProvider } from '@/auth/AuthProvider'
import { RequireAuth } from '@/auth/RequireAuth'
import { ApiError } from '@/lib/api'
import { LoginPage } from '@/pages/LoginPage'
import { UploadPage } from '@/pages/UploadPage'
import { UploadsPage } from '@/pages/UploadsPage'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // An upload's analysis never changes after it's stored, so there's nothing to re-check.
      refetchOnWindowFocus: false,
      // 4xx errors (not found, bad input, not logged in) won't fix themselves on retry.
      retry: (failureCount, error) =>
        !(error instanceof ApiError && error.status < 500) && failureCount < 2,
    },
  },
})

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      { path: '/uploads', element: <UploadsPage /> },
      { path: '/uploads/:uploadId', element: <UploadPage /> },
    ],
  },
  { path: '*', element: <Navigate to="/uploads" replace /> },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
)
