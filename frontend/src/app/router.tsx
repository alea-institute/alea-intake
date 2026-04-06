import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppShell } from '@/shared/components/AppShell'

export const router = createBrowserRouter([
  {
    path: '/',
    Component: AppShell,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
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
    ],
  },
])
