# MPLAD Anomaly Detector — Frontend

Next.js 14 (App Router) + TailwindCSS dashboard UI. All data comes from
`src/lib/api.ts` (mock today; swap for real HTTP later).

## Scripts

```bash
npm install
npm run dev      # http://localhost:3000
npm run build
npm start
```

## Routes

| Path | Description |
|------|-------------|
| `/dashboard` | Filterable project table with risk badges |
| `/dashboard/[projectId]` | Detail, timeline, flags, image placeholders |
| `/map` | Leaflet map with risk-colored markers |
| `/review-queue` | Confirm / dismiss pending flags (local mock state) |
| `/health` | `{ "status": "ok" }` for Docker |

## Swapping mock → API

Replace implementations inside `src/lib/api.ts` only — keep function names
(`getProjects`, `getProjectById`, `getAnomalyFlags`, …).
