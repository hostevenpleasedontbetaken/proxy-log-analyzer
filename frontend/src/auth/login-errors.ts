import { FirebaseError } from 'firebase/app'

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
