# Sable Desktop

Native desktop chat interface for SableCore, built with Electron + React + Vite.

## Prerequisites

- **Node.js 18+** and npm
- **SableCore agent running** with the gateway enabled (default port 8789)

## Quick Start

```bash
# Install dependencies
npm install

# Run in development mode (opens Electron + Vite dev server)
npm run dev
```

The desktop app connects to the SableCore gateway via WebSocket at `ws://localhost:8789`.

## Build

```bash
# Build the web assets (Vite)
npm run build

# Run the built app
npm start
```

## How It Works

- **Frontend**: React SPA with zustand state management, renders in Electron's BrowserWindow
- **Backend**: Connects to SableCore's WebSocket gateway (same one the web dashboard uses)
- **Protocol**: Sends `{ type: "message", text: "..." }` → receives `{ type: "message.done", text: "..." }`

## Configuration

The app reads the gateway URL from the environment or defaults to `ws://localhost:8789`:

```bash
# Connect to a different host/port
OPENSABLE_API_URL=ws://192.168.1.100:8789 npm run dev
```

When running multiple agent profiles, each profile uses a different `WEBCHAT_PORT` in its `profile.env`. Point the desktop app to the desired agent's port.

## Project Structure

```
desktop/
├── electron/          # Electron main process (main.cjs)
├── src/               # React app source
│   ├── hooks/         # useSable.js — WebSocket + zustand store
│   ├── components/    # Chat UI components
│   └── App.jsx        # Root component
├── public/            # Static assets
├── index.html         # Vite entry point
├── vite.config.mjs    # Vite config
└── package.json
```
