import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppShell } from '@/shared/components/AppShell'
import { RequireAuth } from '@/features/auth/RequireAuth'
import { RequireConsent } from '@/features/auth/RequireConsent'

export const router = createBrowserRouter([
  {
    path: '/',
    Component: AppShell,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      // Public routes (no auth required)
      {
        path: 'login',
        lazy: async () => {
          const m = await import('@/features/auth/LoginPage')
          return { Component: m.LoginPage }
        },
      },
      {
        path: 'oauth/finish',
        lazy: async () => {
          const m = await import('@/features/auth/OAuthFinishPage')
          return { Component: m.OAuthFinishPage }
        },
      },
      // Protected routes (require authentication)
      {
        Component: RequireAuth,
        children: [
          // Consent page — accessible after auth but before consent is granted
          {
            path: 'consent',
            lazy: async () => {
              const m = await import('@/features/auth/ConsentPage')
              return { Component: m.ConsentPage }
            },
          },
          // Routes that require both auth AND active consent
          {
            Component: RequireConsent,
            children: [
              {
                path: 'chat/:sessionId',
                lazy: async () => {
                  const m = await import('@/features/chat/ChatPage')
                  return { Component: m.ChatPage }
                },
              },
              {
                path: 'dashboard',
                lazy: async () => {
                  const m = await import('@/features/dashboard/DashboardPage')
                  return { Component: m.DashboardPage }
                },
              },
              {
                path: 'admin/*',
                lazy: async () => {
                  const m = await import('@/features/admin/AdminRouter')
                  return { Component: m.AdminRouter }
                },
              },
              {
                path: 'intake/:id/output',
                lazy: async () => {
                  const m = await import('@/features/output/OutputPage')
                  return { Component: m.OutputPage }
                },
              },
              {
                path: 'intake/:id/visualization',
                lazy: async () => {
                  const m = await import('@/features/visualization/VisualizationPage')
                  return { Component: m.VisualizationPage }
                },
              },
            ],
          },
        ],
      },
    ],
  },
])
