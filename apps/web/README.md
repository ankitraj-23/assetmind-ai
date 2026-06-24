# AssetMind AI — Web

Demo-ready Next.js (App Router) + TypeScript + Tailwind CSS frontend shell for
AssetMind AI. Currently renders **mock data** to showcase the product flow:

Dashboard → Documents → Upload → Assets → Asset Detail → Copilot → RCA → Compliance

## Getting started

```bash
cd apps/web
npm install
npm run dev
```

Open http://localhost:3000

## Notes

- Mock data lives in `src/lib/mock-data.ts`.
- `src/lib/api.ts` contains placeholder helpers describing the intended backend
  contract (FastAPI at `http://localhost:8000`). These are **not wired into the
  UI yet** — the shell is presentation-only.
- Set `NEXT_PUBLIC_API_BASE_URL` to override the backend URL when integration begins.
