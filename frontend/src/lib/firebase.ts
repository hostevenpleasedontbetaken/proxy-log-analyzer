import { initializeApp } from 'firebase/app'
import { browserSessionPersistence, connectAuthEmulator, initializeAuth } from 'firebase/auth'

// These values identify the Firebase project; they are not secrets. Security comes from the
// backend verifying every ID token, and from public sign-up being disabled.
const app = initializeApp({
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
})

// Session persistence: the login lives only as long as the browser tab (Phase 3 XSS decision).
export const auth = initializeAuth(app, { persistence: browserSessionPersistence })

const emulatorUrl = import.meta.env.VITE_AUTH_EMULATOR_URL
if (emulatorUrl) {
  // Local dev only: talk to the fake Firebase Auth server from docker compose.
  connectAuthEmulator(auth, emulatorUrl, { disableWarnings: true })
}
