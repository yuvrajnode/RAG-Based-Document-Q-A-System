# Verbatim web client

React 18 + TypeScript + Vite + Tailwind. No component library, no state
management library, no markdown parser - the app is small enough that each of
those would be more code than the thing it replaces.

```bash
npm install
npm run dev     # :5173, proxying /api to http://127.0.0.1:8000
npm run build   # emits dist/, which the FastAPI app serves at / when present
```

Layout: document library on the left, conversation in the middle, retrieved
passages on the right. Below the `lg` breakpoint the three become tabs.

Notes on a couple of decisions:

- **SSE is read manually** in `src/lib/api.ts`. `EventSource` only issues GET
  requests and cannot carry the question body.
- **Auto-scroll unpins** as soon as the reader scrolls up. Being dragged back
  to the bottom mid-stream while reading a source is the fastest way to make a
  chat UI feel hostile.
- **Uploads run sequentially.** Ingestion is CPU-bound, so a parallel drop of
  twenty files only queues behind itself with a worse progress readout.
