'use client'
// frontend/components/UploadZone.tsx

import { useRef, useState, useEffect } from 'react'
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

function CheckCircleIcon() {
  return (
    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" className="text-[#0f6e56]">
      <circle cx="12" cy="12" r="10" fill="#e6f2ef" />
      <path
        d="M8.5 12.5L10.5 14.5L15.5 9.5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export default function UploadZone({ onUploadSuccess }: UploadZoneProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [showCheck, setShowCheck] = useState(false) // For the green checkmark
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
    
    // Show green checkmark animation first
    setShowCheck(true)
    setTimeout(() => {
      setShowCheck(false)
      setSelectedFile(file)
    }, 800)
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
    relative border-2 rounded-xl p-8 text-center cursor-pointer transition-all duration-300 transform
    ${isDragging
      ? 'border-teal bg-teal-light border-solid scale-102 shadow-md'
      : 'border-gray-300 border-dashed hover:border-teal hover:bg-teal-light/40 hover:-translate-y-0.5 shadow-sm hover:shadow-md'}
    ${isUploading || showCheck ? 'pointer-events-none' : ''}
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
        onClick={() => !isUploading && !showCheck && fileInputRef.current?.click()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {isUploading ? (
          // Uploading state
          <div className="flex flex-col items-center gap-4 py-2">
            <p className="text-sm font-medium text-[#1a2744]">Uploading and queuing…</p>
            {/* Striped progress bar in teal */}
            <div className="w-full max-w-sm h-3 bg-gray-100 rounded-full overflow-hidden relative">
              <div 
                className="absolute top-0 left-0 h-full w-full bg-teal animate-shimmer"
                style={{
                  backgroundImage: 'linear-gradient(45deg, rgba(255,255,255,0.15) 25%, transparent 25%, transparent 50%, rgba(255,255,255,0.15) 50%, rgba(255,255,255,0.15) 75%, transparent 75%, transparent)',
                  backgroundSize: '1rem 1rem',
                  animation: 'shimmer 1s linear infinite'
                }}
              />
            </div>
          </div>
        ) : showCheck ? (
          // Temporary Checkmark Animation State
             <div className="flex flex-col items-center justify-center gap-3 py-4 animate-pop-in">
                <CheckCircleIcon />
                <p className="text-sm font-medium text-teal">File loaded</p>
             </div>
        ) : selectedFile ? (
          // File selected state
          <div
            className="flex flex-col items-center gap-3 animate-slide-up"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 bg-white border border-gray-200 shadow-sm
                            rounded-lg px-4 py-3 w-full max-w-sm transition-all hover:border-teal/50">
              <div className="w-8 h-8 bg-teal-light rounded-full flex items-center justify-center flex-shrink-0">
                <FileIcon />
              </div>
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
                className="text-gray-400 hover:text-red-custom hover:bg-red-custom/10 w-6 h-6 rounded flex items-center justify-center transition-colors text-lg leading-none"
                aria-label="Remove file"
              >
                ×
              </button>
            </div>
            <button
              onClick={handleUpload}
              className="w-full max-w-sm bg-teal hover:bg-teal-dark shadow-sm hover:shadow text-white text-sm
                         font-medium rounded-lg py-3 mt-1 transition-all transform hover:-translate-y-0.5"
            >
              Analyze drafted document
            </button>
          </div>
        ) : (
          // Empty state
          <div className="flex flex-col items-center gap-4 py-2">
            <div className="relative">
              <div className="absolute inset-0 rounded-full animate-pulse-ring" />
              <div className="w-14 h-14 rounded-full bg-teal-light flex items-center
                              justify-center relative z-10 border border-teal/20">
                <UploadIcon />
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold text-[#1a2744]">
                Select a draft to analyze
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Drag and drop or click to browse · PDF format only · Max {MAX_UPLOAD_MB}MB
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Error message */}
      {error && (
        <div className="mt-3 text-sm text-red-custom bg-red-custom/5 border border-red-custom/20 rounded-lg px-4 py-3 flex items-start gap-2 animate-pop-in">
          <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span className="font-medium">{error}</span>
        </div>
      )}
    </div>
  )
}
