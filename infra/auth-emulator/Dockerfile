# The Firebase Auth emulator: a fake Firebase login server for local development.
# It issues tokens that only work while FIREBASE_AUTH_EMULATOR_HOST is set (never in production).
FROM node:24-slim
RUN npm install -g firebase-tools@15.34.2 && npm cache clean --force \
    # Download the emulator web UI now instead of on every container start.
    && firebase setup:emulators:ui
WORKDIR /srv
COPY firebase.json ./
# The demo user (demo@example.com). Regenerate by exporting from a running emulator.
COPY seed ./seed
# --import loads the seed on every start, so local login is always the same.
CMD ["firebase", "emulators:start", "--only", "auth", "--project", "demo-proxylog", "--import", "/srv/seed"]
