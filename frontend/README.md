# Frontend

Vue 3 + TypeScript (Vite) UI for the agents in [`../agents`](../agents).
It talks only to the Flask backend in [`../backend`](../backend).

## Run

```bash
npm install
npm run dev
npm run build
```

The backend must be reachable. `npm run dev` proxies `/api` and `/health` to
`http://localhost:5000`. Can be overridden with `VITE_DEV_API_TARGET`.

```bash
docker compose up --build frontend
```
