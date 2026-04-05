'use client'
// frontend/app/(auth)/login/page.tsx

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '../../../lib/supabase'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    const { error: signInError } = await supabase.auth.signInWithPassword({
      email,
      password,
    })

    if (signInError) {
      setError(signInError.message)
      setLoading(false)
    } else {
      router.push('/dashboard')
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Left column — navy, hidden on mobile */}
      <div className="hidden lg:flex lg:w-1/2 bg-navy flex-col justify-between p-12">
        <div>
          <span className="text-teal text-xl font-medium tracking-tight">
            ScrutinyAI
          </span>
        </div>

        <div className="space-y-10">
          <div>
            <h1 className="text-white text-3xl font-medium leading-tight mb-4">
              Know your objections<br />before the registry does.
            </h1>
            <p className="text-slate text-sm leading-relaxed max-w-xs">
              Upload your civil draft and receive a ranked objection report aligned
              with Karnataka High Court filing requirements — before you walk to the counter.
            </p>
          </div>

          <ul className="space-y-4 pt-10">
            {[
              '21-point Karnataka HC checklist',
              'Results in under 5 minutes',
              'Documents never leave India',
            ].map((point) => (
              <li key={point} className="flex items-center gap-3">
                <span className="w-5 h-5 rounded-full border border-teal flex items-center justify-center flex-shrink-0">
                  <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                    <path
                      d="M1 4L3.5 6.5L9 1"
                      stroke="#0f6e56"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
                <span className="text-slate text-sm">{point}</span>
              </li>
            ))}
          </ul>
        </div>

        <p className="text-slate text-xs">
          © {new Date().getFullYear()} ScrutinyAI. For Karnataka advocates.
        </p>
      </div>

      {/* Right column — login card */}
      <div className="flex-1 flex items-center justify-center bg-gray-50 p-6">
        <div className="w-full max-w-sm">
          <div className="bg-white border border-gray-200 rounded-lg p-8 space-y-6">
            {/* Logo */}
            <div>
              <p className="text-teal text-base font-medium">ScrutinyAI</p>
              <p className="text-gray-text text-xs mt-1">
                High Court of Karnataka — Advocate Portal
              </p>
            </div>

            {/* Form */}
            <form onSubmit={handleSignIn} className="space-y-4">
              <div>
                <label
                  htmlFor="email"
                  className="block text-xs font-medium text-gray-600 mb-1.5"
                >
                  Email address
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm
                             focus:outline-none focus:border-teal transition-colors"
                  placeholder="you@chamber.in"
                />
              </div>

              <div>
                <label
                  htmlFor="password"
                  className="block text-xs font-medium text-gray-600 mb-1.5"
                >
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm
                             focus:outline-none focus:border-teal transition-colors"
                  placeholder="••••••••"
                />
              </div>

              {error && (
                <p className="text-red-custom text-xs leading-relaxed bg-red-custom/5 border border-red-custom/20 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-teal hover:bg-teal-dark text-white text-sm font-medium
                           rounded-lg py-2.5 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg
                      className="animate-spin h-4 w-4 text-white"
                      viewBox="0 0 24 24"
                      fill="none"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8v8H4z"
                      />
                    </svg>
                    Signing in…
                  </span>
                ) : (
                  'Sign in'
                )}
              </button>
            </form>

            {/* Divider */}
            {/* Footer note */}
            <p className="text-center text-gray-text text-xs leading-relaxed">
              Don't have an account?{' '}
              <button
                onClick={(e) => { e.preventDefault(); router.push('/register') }}
                className="text-teal hover:underline font-medium cursor-pointer"
              >
                Register now
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
