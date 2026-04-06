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
  http.post('/api/v1/auth/login', () =>
    HttpResponse.json({
      access_token: 'tok',
      user: { id: 'u1', email: 'test@example.com', role: 'consumer', org_id: '1' },
    })
  ),
  http.post('/api/v1/auth/oauth/exchange', () =>
    HttpResponse.json({
      access_token: 'sso-tok',
      user: { id: 'u1', email: 'sso@example.com', role: 'consumer', org_id: '1' },
    })
  ),
]
