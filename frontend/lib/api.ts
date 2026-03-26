// frontend/lib/api.ts
import { supabase } from './supabase'
import type { CheckResult, JobStatus, UploadResponse } from '../types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function getAuthHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `Request failed: ${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) message = body.detail
      else if (body?.message) message = body.message
    } catch {
      // ignore parse error, keep default message
    }
    throw new Error(message)
  }
  return res.json() as Promise<T>
}

export async function uploadPDF(file: File): Promise<UploadResponse> {
  const authHeaders = await getAuthHeader()
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${BASE_URL}/upload`, {
    method: 'POST',
    headers: { ...authHeaders },
    body: formData,
  })
  return handleResponse<UploadResponse>(res)
}

export async function getStatus(jobId: string): Promise<JobStatus> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${BASE_URL}/status/${jobId}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders },
  })
  return handleResponse<JobStatus>(res)
}

export async function getReport(jobId: string): Promise<CheckResult> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${BASE_URL}/report/${jobId}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders },
  })
  return handleResponse<CheckResult>(res)
}

export async function submitFeedback(
  objectionId: string,
  jobId: string,
  isCorrect: boolean
): Promise<void> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${BASE_URL}/feedback/${objectionId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body: JSON.stringify({ is_correct: isCorrect, job_id: jobId }),
  })
  await handleResponse<{ status: string }>(res)
}
