'use client'
// frontend/components/UploadZone.tsx

import { useRef, useState } from 'react'
import type { RecentCheck } from '../types'
import { uploadPDF } from '../lib/api'

const MAX_UPLOAD_MB = 100

interface UploadZoneProps {
  onUploadSuccess: (job: RecentCheck) => void
}

function formatFileSize(bytes: number): string {
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

// Inline SVG icons
function UploadIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
      <path
        d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"
        stroke="#0f6e56"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function FileIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <path
        d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z"
        stroke="#0f6e56"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M14 2v6h6" stroke="#0f6e56" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

export default function UploadZone({ onUploadSuccess }: UploadZoneProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const validateAndSetFile = (file: File) => {
    setError(null)
    if (!file.type.includes('pdf') && !file.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF files are accepted.')
      return
    }
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setError(`File exceeds ${MAX_UPLOAD_MB}MB limit.`)
      return
    }
    setSelectedFile(file)
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }
  const handleDragLeave = () => setIsDragging(false)
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) validateAndSetFile(file)
  }
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) validateAndSetFile(file)
  }

  const handleUpload = async () => {
    if (!selectedFile || isUploading) return
    setIsUploading(true)
    setError(null)

    try {
      const response = await uploadPDF(selectedFile)
      const newJob: RecentCheck = {
        job_id: response.job_id,
        filename: response.filename,
        created_at: new Date().toISOString(),
        status: 'queued',
      }
      onUploadSuccess(newJob)
      setSelectedFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed. Please try again.')
    } finally {
      setIsUploading(false)
    }
  }

  const zoneClasses = `
    relative border-2 rounded-xl p-8 text-center cursor-pointer transition-all duration-150
    ${isDragging
      ? 'border-teal bg-teal-light border-solid'
      : 'border-gray-300 border-dashed hover:border-teal hover:bg-teal-light/40'}
    ${isUploading ? 'pointer-events-none opacity-70' : ''}
  `

  return (
    <div className="mb-8">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="hidden"
        onChange={handleInputChange}
      />

      {/* Drop zone */}
      <div
        className={zoneClasses}
        onClick={() => !isUploading && fileInputRef.current?.click()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {isUploading ? (
          // Uploading state
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-teal-light flex items-center justify-center">
              <svg className="animate-spin h-5 w-5 text-teal" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            </div>
            <p className="text-sm text-teal font-medium">Uploading and queuing…</p>
          </div>
        ) : selectedFile ? (
          // File selected state
          <div
            className="flex flex-col items-center gap-3"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 bg-white border border-gray-200
                            rounded-lg px-4 py-3 w-full max-w-sm">
              <FileIcon />
              <div className="flex-1 min-w-0 text-left">
                <p className="text-sm font-medium text-[#1a2744] truncate">
                  {selectedFile.name}
                </p>
                <p className="text-xs text-gray-text mt-0.5">
                  {formatFileSize(selectedFile.size)}
                </p>
              </div>
              <button
                onClick={() => setSelectedFile(null)}
                className="text-gray-400 hover:text-gray-600 text-lg leading-none"
                aria-label="Remove file"
              >
                ×
              </button>
            </div>
            <button
              onClick={handleUpload}
              className="w-full max-w-sm bg-teal hover:bg-teal-dark text-white text-sm
                         font-medium rounded-lg py-2.5 transition-colors"
            >
              Check this draft
            </button>
          </div>
        ) : (
          // Empty state
          <div className="flex flex-col items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-teal-light flex items-center
                            justify-center">
              <UploadIcon />
            </div>
            <div>
              <p className="text-sm font-medium text-[#1a2744]">
                Drop your civil draft here
              </p>
              <p className="text-xs text-gray-text mt-1">
                or click to browse · PDF only · max {MAX_UPLOAD_MB}MB
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Error message */}
      {error && (
        <p className="mt-2 text-xs text-red-custom bg-red-custom/5 border border-red-custom/20
                      rounded-lg px-3 py-2">
          {error}
        </p>
      )}
    </div>
  )
}
