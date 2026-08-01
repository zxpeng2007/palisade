# Murus web client

Vite 5 + Svelte 4 + TypeScript. No runtime dependencies — the board, router,
and websocket layer are hand-rolled against [API.md](../API.md).

## Requirements

- Node.js 18.17+ (20 LTS recommended)
- npm

## Develop

```sh
cd web
npm install
npm run dev
```

The dev server runs at http://localhost:5173 and proxies `/api` and `/ws` to
the Murus server at http://localhost:8000, so start that first:

```sh
uvicorn murus.app:app --host 0.0.0.0 --port 8000
```

## Build

```sh
cd web
npm install
npm run build
```

The build lands in `web/dist`. The server serves it automatically: if
`web/dist` exists when the FastAPI app starts, it is mounted at `/` (see
`server/murus/app.py`), so production needs no separate web server.

## Type check (optional)

```sh
npm run check
```
