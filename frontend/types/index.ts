// frontend/types/index.ts

export interface Objection {
  id: string
  category: 'FORMAT' | 'STRUCTURE' | 'FISCAL'
  severity: 'CRITICAL' | 'MAJOR' | 'MINOR'
  checklist_point_id: string
  page_references: number[]
  rule_citation: string
  description: string
  suggested_fix: string
  confidence_score: number
  requires_manual_verification: boolean
}

export interface CheckResult {
  job_id: string
  filename: string
  checked_at: string
  checklist_version: string
  total_ai_tokens_used: number
  critical_count: number
  major_count: number
  minor_count: number
  objections: Objection[]
}

export interface JobStatus {
  job_id: string
  status: 'queued' | 'processing' | 'complete' | 'failed'
  progress_percent: number
  filename: string
  created_at: string
  error_message: string | null
}

export interface UploadResponse {
  job_id: string
  status: string
  filename: string
}

export interface RecentCheck {
  job_id: string
  filename: string
  created_at: string
  status: 'queued' | 'processing' | 'complete' | 'failed'
  progress_percent?: number
}
