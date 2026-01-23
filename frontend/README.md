# Frontend (Next.js)

Minimal UI to query the ranking service and render movie cards.

## Run
```bash
npm run dev
```

Default API target is `http://localhost:8080`. To override:
```bash
NEXT_PUBLIC_API_BASE=http://localhost:8080 npm run dev
```

## Notes
- This is a client-only page that calls `/rank` on the Go service.
- If you see CORS errors, ensure the Go server is running and reachable.
