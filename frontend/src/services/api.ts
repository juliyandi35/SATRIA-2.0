import type { ActualRecord, Filters, ReferenceRecord } from '../types'

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  const payload = await response.json().catch(() => ({ error: 'Respons server tidak dapat dibaca.' }))
  if (response.status === 401 && !url.startsWith('/api/auth/')) {
    window.dispatchEvent(new Event('satria:unauthorized'))
  }
  if (!response.ok) {
    throw new Error(payload.error || payload.message || `Permintaan gagal (${response.status}).`)
  }
  return payload as T
}

const jsonPost = <T>(url: string, body: unknown) =>
  requestJson<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

export const api = {
  dataStatus: () => requestJson<Record<string, unknown>>('/api/data/status'),
  importBuiltin: () => jsonPost<Record<string, unknown>>('/api/data/import', { source: 'builtin' }),
  resetData: () => jsonPost<Record<string, unknown>>('/api/data/reset', {}),
  dataView: (payload: Record<string, unknown>) => jsonPost('/api/data/view', payload),
  diagnostics: (filters: Filters) => jsonPost('/api/data/diagnostics', { filters }),
  spatial: (filters: Filters, epsilonKm = 150, minSamples = 3) =>
    jsonPost('/api/spatial/clusters', { filters, epsilon_km: epsilonKm, min_samples: minSamples }),
  predictive: (filters: Filters) => jsonPost('/api/predictive/forecast', { filters }),
  models: () => requestJson<{ provider: string; models: unknown[] }>('/api/models'),
  systemStatus: () => requestJson<Record<string, unknown>>('/api/system/status'),
  dbTest: () => requestJson<Record<string, unknown>>('/api/db/test'),
  clearLogs: () => jsonPost<Record<string, unknown>>('/api/logs/clear', {}),
  emailReport: (email: string, filters: Filters) => jsonPost<Record<string, unknown>>('/api/email/report', { email, filters }),
  emailAuditLog: (email: string) => jsonPost<Record<string, unknown>>('/api/email/audit-log', { email }),
  chat: (payload: Record<string, unknown>) => jsonPost<{ response: string }>('/api/chat', payload),
  clearChat: (sessionId: string) => jsonPost('/api/chat/session/clear', { session_id: sessionId }),
  dataActual: (page: number, pageSize: number) =>
    requestJson<{ records: ActualRecord[]; pagination: { page: number; page_size: number; total_records: number; total_pages: number } }>(
      `/api/data/actual?page=${page}&page_size=${pageSize}`,
    ),
  updateActual: (unitNode: string, location: string, fields: Partial<Record<string, number>>) =>
    jsonPost<{ status: string; record: ActualRecord }>('/api/data/actual/update', { unit_node: unitNode, location, ...fields }),
  importActual: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return requestJson<{ status: string; rows: number; metadata: Record<string, unknown> }>('/api/data/actual/import', { method: 'POST', body: form })
  },
  overrideStatus: (unitNode: string, location: string, category: string, status: string) =>
    jsonPost<{ status: string; record: { unit_node: string; location: string; category: string; status: string } }>(
      '/api/data/status/override',
      { unit_node: unitNode, location, category, status },
    ),
  dataReference: () => requestJson<{ records: ReferenceRecord[] }>('/api/data/reference'),
  updateReference: (unitType: string, fields: Partial<Record<string, number>>) =>
    jsonPost<{ status: string; record: ReferenceRecord }>('/api/data/reference/update', { unit_type: unitType, ...fields }),
  auth: {
    status: () => requestJson<{ configured: boolean }>('/api/auth/status'),
    session: () => requestJson<{ authenticated: boolean; email: string | null }>('/api/auth/session'),
    setup: (email: string, password: string) =>
      jsonPost<{ status: string; email: string; totp_secret: string; provisioning_uri: string }>('/api/auth/setup', { email, password }),
    enrollMfa: (email: string, code: string, remember = false) =>
      jsonPost<{ status: string; email: string }>('/api/auth/mfa/enroll', { email, code, remember }),
    login: (email: string, password: string, totpCode: string, remember = false) =>
      jsonPost<{ status: string; email: string }>('/api/auth/login', { email, password, totp_code: totpCode, remember }),
    logout: () => jsonPost<{ status: string }>('/api/auth/logout', {}),
    changePassword: (currentPassword: string, newPassword: string) =>
      jsonPost<{ status: string }>('/api/auth/change-password', { current_password: currentPassword, new_password: newPassword }),
    changeEmail: (currentPassword: string, newEmail: string) =>
      jsonPost<{ status: string; email: string }>('/api/auth/change-email', { current_password: currentPassword, new_email: newEmail }),
    accounts: () => requestJson<{ accounts: { email: string; mfa_enabled: boolean; created_at: string }[] }>('/api/auth/accounts'),
    addAccount: (currentPassword: string, newEmail: string, newPassword: string) =>
      jsonPost<{ status: string; email: string; totp_secret: string; provisioning_uri: string }>('/api/auth/accounts/add', {
        current_password: currentPassword,
        new_email: newEmail,
        new_password: newPassword,
      }),
    removeAccount: (currentPassword: string, targetEmail: string) =>
      jsonPost<{ status: string; removed_self: boolean }>('/api/auth/accounts/remove', {
        current_password: currentPassword,
        target_email: targetEmail,
      }),
  },
}
