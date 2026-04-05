import { http, HttpResponse } from 'msw'

export const handlers = [
  http.get('/api/v1/auth/me', () =>
    HttpResponse.json({
      id: 'u1',
      email: 'test@example.com',
      role: 'consumer',
    })
  ),
  http.post('/api/v1/auth/refresh', () =>
    HttpResponse.json({
      access_token: 'tok',
      user: { id: 'u1' },
    })
  ),
  http.get('/api/v1/intakes', () =>
    HttpResponse.json({ items: [], total: 0 })
  ),
]
