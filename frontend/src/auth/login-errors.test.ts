import { FirebaseError } from 'firebase/app'
import { describe, expect, it } from 'vitest'
import { guestErrorMessage, loginErrorMessage, signupErrorMessage } from '@/auth/login-errors'

describe('loginErrorMessage', () => {
  it('uses one message for unknown user and wrong password', () => {
    const codes = ['auth/wrong-password', 'auth/user-not-found', 'auth/invalid-credential']
    const messages = codes.map((code) => loginErrorMessage(new FirebaseError(code, 'x')))
    expect(new Set(messages)).toEqual(new Set(['Wrong email or password.']))
  })

  it('says when the sign-in service is unreachable', () => {
    expect(loginErrorMessage(new FirebaseError('auth/network-request-failed', 'x'))).toMatch(/reach/)
  })

  it('handles non-Firebase errors', () => {
    expect(loginErrorMessage(new Error('boom'))).toBe('Could not sign in.')
  })
})

describe('guestErrorMessage', () => {
  it('says the demo is unavailable when anonymous sign-in is off', () => {
    const err = new FirebaseError('auth/admin-restricted-operation', 'x')
    expect(guestErrorMessage(err)).toMatch(/demo isn’t available/)
  })

  it('still reports a network problem as one', () => {
    expect(guestErrorMessage(new FirebaseError('auth/network-request-failed', 'x'))).toMatch(/reach/)
  })
})

describe('signupErrorMessage', () => {
  it('explains the common sign-up problems', () => {
    const msg = (code: string) => signupErrorMessage(new FirebaseError(code, 'x'))
    expect(msg('auth/email-already-in-use')).toMatch(/already exists/)
    expect(msg('auth/weak-password')).toMatch(/6 characters/)
    expect(msg('auth/invalid-email')).toMatch(/valid email/)
  })

  it('falls back to a general message', () => {
    expect(signupErrorMessage(new Error('boom'))).toMatch(/Could not create/)
  })
})
