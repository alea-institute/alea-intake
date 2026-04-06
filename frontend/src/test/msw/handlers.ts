import { http, HttpResponse } from 'msw'
import { mockVisualizationData } from '../fixtures/visualization'

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
  http.get('/api/v1/orgs/:id', () =>
    HttpResponse.json({
      id: 'org1',
      name: 'Test Org',
      deployment_type: 'law_firm',
    })
  ),
  http.put('/api/v1/orgs/:id', () =>
    HttpResponse.json({
      id: 'org1',
      name: 'Updated Org',
      deployment_type: 'law_firm',
    })
  ),
  http.get('/api/v1/outputs/:id', () =>
    HttpResponse.json({
      profiles: [
        {
          profile_key: 'law_firm_memo',
          content: '# Memo\n\nSample output.',
          rendered_at: '2026-04-01T00:00:00Z',
        },
      ],
    })
  ),
  http.get('/api/v1/outputs/:id/export', () =>
    new HttpResponse(new Blob(['pdf-data']), {
      headers: { 'Content-Type': 'application/pdf' },
    })
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
  http.get('/api/v1/analysis/:id/visualization', () =>
    HttpResponse.json(mockVisualizationData)
  ),
]
