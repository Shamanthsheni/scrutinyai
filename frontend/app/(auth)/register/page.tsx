'use client'
// frontend/app/(auth)/register/page.tsx

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '../../../lib/supabase'

export default function RegisterPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(false)
    
    if (password !== confirmPassword) {
      setError("Passwords do not match.")
      return
    }

    setLoading(true)

    const { error: signUpError } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: `${window.location.origin}/login`,
      }
    })

    if (signUpError) {
      setError(signUpError.message)
      setLoading(false)
    } else {
      setSuccess(true)
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Left column — navy, hidden on mobile */}
      <div className="hidden lg:flex lg:w-1/2 bg-[#0b172a] relative overflow-hidden flex-col justify-between p-12">
        <div className="absolute inset-0 grid-pattern-overlay opacity-30 pointer-events-none" />
        <div className="relative z-10">
          <span className="text-teal-light text-xl font-medium tracking-tight">
            ScrutinyAI
          </span>
        </div>

        <div className="space-y-10 relative z-10">
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

        <p className="text-slate text-xs relative z-10">
          © {new Date().getFullYear()} ScrutinyAI. For Karnataka advocates.
        </p>
      </div>

      {/* Right column — register card */}
      <div className="flex-1 flex items-center justify-center bg-gray-50 p-6 relative">
        <div className="w-full max-w-sm">
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-8 space-y-6">
            {/* Logo */}
            <div>
              <p className="text-teal text-sm font-semibold tracking-wide uppercase">ScrutinyAI</p>
              <h2 className="text-[#1a2744] text-2xl font-semibold mt-1 tracking-tight">
                Create an account
              </h2>
            </div>

            {/* Form */}
            {!success ? (
              <form onSubmit={handleSignUp} className="space-y-4">
                <div>
                  <label htmlFor="email" className="block text-xs font-semibold text-gray-600 mb-1.5 uppercase tracking-wide">
                    Email address
                  </label>
                  <input
                    id="email"
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus:border-teal transition-colors shadow-sm"
                    placeholder="you@chamber.in"
                  />
                </div>

                <div>
                  <label htmlFor="password" className="block text-xs font-semibold text-gray-600 mb-1.5 uppercase tracking-wide">
                    Password
                  </label>
                  <input
                    id="password"
                    type="password"
                    autoComplete="new-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus:border-teal transition-colors shadow-sm"
                    placeholder="••••••••"
                  />
                </div>

                <div>
                  <label htmlFor="confirmPassword" className="block text-xs font-semibold text-gray-600 mb-1.5 uppercase tracking-wide">
                    Confirm Password
                  </label>
                  <input
                    id="confirmPassword"
                    type="password"
                    autoComplete="new-password"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus:border-teal transition-colors shadow-sm"
                    placeholder="••••••••"
                  />
                </div>

                {error && (
                  <p className="text-red-custom text-xs leading-relaxed bg-red-custom/5 border border-red-custom/20 rounded-lg px-3 py-2 animate-pop-in">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-teal shadow-sm hover:shadow hover:bg-teal-dark hover:-translate-y-0.5 text-white text-sm font-semibold rounded-lg py-3 transition-all disabled:opacity-60 disabled:cursor-not-allowed mt-2"
                >
                  {loading ? 'Creating account…' : 'Create account'}
                </button>
              </form>
            ) : (
              <div className="bg-teal-light/50 border border-teal/20 rounded-lg p-5 text-center px-4 animate-pop-in">
                <div className="w-12 h-12 rounded-full bg-teal text-white flex items-center justify-center mx-auto mb-4 shadow-sm border-2 border-white pointer-events-none">
                  <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                     <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h3 className="text-base font-semibold text-teal-dark mb-1">Check your email</h3>
                <p className="text-xs text-teal/80 leading-relaxed mb-6">
                  We've sent a verification link to <strong>{email}</strong>. Please confirm your email to continue.
                </p>
                <button
                  type="button"
                  onClick={() => router.push('/login')}
                  className="text-sm font-semibold text-teal border border-teal/20 bg-white rounded-lg px-4 py-2 hover:bg-teal-light transition-colors shadow-sm"
                >
                  Return to sign in
                </button>
              </div>
            )}

            {/* Footer note */}
            {!success && (
              <p className="text-center text-gray-text text-sm leading-relaxed mt-2">
                Already have an account?{' '}
                <button
                  onClick={(e) => { e.preventDefault(); router.push('/login') }}
                  className="text-teal hover:underline font-semibold cursor-pointer"
                >
                  Sign in
                </button>
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
