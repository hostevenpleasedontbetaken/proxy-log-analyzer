import { FirebaseError } from 'firebase/app'

/** Turns a failed "Create account" into text for the login form. */
export function signupErrorMessage(err: unknown): string {
  if (!(err instanceof FirebaseError)) return 'Could not create the account. Please try again.'
  switch (err.code) {
    case 'auth/email-already-in-use':
      return 'An account with that email already exists. Try signing in instead.'
    case 'auth/weak-password':
      return 'Choose a password of at least 6 characters.'
    case 'auth/invalid-email':
      return 'Enter a valid email address.'
    case 'auth/network-request-failed':
      return loginErrorMessage(err)
    default:
      return 'Could not create the account. Please try again.'
  }
}

/** Turns a failed "Try the demo" (anonymous sign-in) into text for the login form. */
export function guestErrorMessage(err: unknown): string {
  if (err instanceof FirebaseError && err.code === 'auth/network-request-failed') {
    return loginErrorMessage(err)
  }
  return 'The demo isn’t available right now. Please try again later.'
}

/** Turns a Firebase sign-in error into text for the login form. */
export function loginErrorMessage(err: unknown): string {
  if (!(err instanceof FirebaseError)) return 'Could not sign in.'
  switch (err.code) {
    case 'auth/network-request-failed':
      return 'Can’t reach the sign-in service. Check your connection and try again.'
    case 'auth/too-many-requests':
      return 'Too many attempts. Wait a minute and try again.'
    default:
      // "No such user" and "wrong password" get the same message on purpose, so the form
      // can't be used to discover which emails have accounts.
      return 'Wrong email or password.'
  }
}
