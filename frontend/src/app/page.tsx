"use client";

import { useMemo, useState } from "react";

type RankResult = {
  movie_id: number;
  score: number;
  title: string;
  poster_url?: string;
  reasons?: string[];
};

type RankResponse = {
  user_id: number;
  results: RankResult[];
  latency_ms?: number;
};

type Status = "idle" | "loading" | "success" | "error";

const FALLBACK_POSTER =
  "data:image/svg+xml;charset=utf-8," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="600">
      <rect width="100%" height="100%" fill="#f2e4d2"/>
      <path d="M0 420 L400 260 L400 600 L0 600 Z" fill="#e7c9a4"/>
      <circle cx="110" cy="160" r="48" fill="#e8772e"/>
      <circle cx="270" cy="170" r="32" fill="#2f6f6d"/>
    </svg>`
  );

export default function Home() {
  const apiBase = useMemo(
    () => process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8080",
    []
  );
  const [userId, setUserId] = useState("123");
  const [k, setK] = useState(12);
  const [results, setResults] = useState<RankResult[]>([]);
  const [latency, setLatency] = useState<number | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);

  const runRank = async (overrideUserId?: number) => {
    const resolvedUserId = overrideUserId ?? Number(userId);
    if (!resolvedUserId || Number.isNaN(resolvedUserId)) {
      setStatus("error");
      setError("Enter a valid user id.");
      return;
    }

    setStatus("loading");
    setError(null);
    setLatency(null);

    try {
      const response = await fetch(`${apiBase}/rank`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: resolvedUserId, k }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = (await response.json()) as RankResponse;
      setResults(data.results ?? []);
      setLatency(data.latency_ms ?? null);
      setStatus("success");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Request failed.");
    }
  };

  const surpriseMe = () => {
    const randomUser = Math.floor(Math.random() * 200000) + 1;
    setUserId(String(randomUser));
    runRank(randomUser);
  };

  return (
    <div className="min-h-screen">
      <div className="fade-grid pointer-events-none fixed inset-0 opacity-40" />
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-6 pb-16 pt-12">
        <header className="flex flex-col gap-6">
          <div className="flex items-center justify-between gap-6">
            <div className="flex flex-col gap-2">
              <p className="text-xs uppercase tracking-[0.3em] text-[color:var(--muted)]">
                Personalized Ranking Service
              </p>
              <h1 className="text-4xl font-semibold text-[color:var(--ink)] md:text-5xl">
                Cinematic picks tuned to each user
              </h1>
            </div>
            <div className="hidden items-center gap-3 rounded-full border border-[color:var(--stroke)] bg-white/70 px-5 py-2 text-xs text-[color:var(--muted)] md:flex">
              <span className="h-2 w-2 rounded-full bg-[color:var(--accent-2)]" />
              Live API: {apiBase}
            </div>
          </div>
          <p className="max-w-2xl text-lg text-[color:var(--muted)]">
            Explore a ranked list of movies for any user. This UI talks to the Go
            ranking service and shows a lightweight explanation for each pick.
          </p>
        </header>

        <div className="grid gap-8 lg:grid-cols-[360px,1fr]">
          <aside className="card flex flex-col gap-6 rounded-3xl p-6">
            <div>
              <h2 className="text-2xl font-semibold">Run a ranking query</h2>
              <p className="mt-2 text-sm text-[color:var(--muted)]">
                Use a MovieLens user id and choose how many results to display.
              </p>
            </div>

            <div className="flex flex-col gap-4">
              <label className="flex flex-col gap-2 text-sm">
                User id
                <input
                  value={userId}
                  onChange={(event) => setUserId(event.target.value)}
                  className="rounded-2xl border border-[color:var(--stroke)] bg-white/80 px-4 py-3 text-base outline-none focus:ring-2 focus:ring-[color:var(--accent)]"
                  placeholder="e.g. 123"
                />
              </label>
              <label className="flex flex-col gap-2 text-sm">
                Top K
                <input
                  value={k}
                  onChange={(event) => setK(Number(event.target.value))}
                  type="number"
                  min={1}
                  max={50}
                  className="rounded-2xl border border-[color:var(--stroke)] bg-white/80 px-4 py-3 text-base outline-none focus:ring-2 focus:ring-[color:var(--accent)]"
                />
              </label>
            </div>

            <div className="flex flex-col gap-3">
              <button
                onClick={() => runRank()}
                className="rounded-full bg-[color:var(--accent)] px-5 py-3 text-sm font-semibold text-white transition hover:brightness-110"
              >
                Get recommendations
              </button>
              <button
                onClick={surpriseMe}
                className="rounded-full border border-[color:var(--stroke)] bg-white/70 px-5 py-3 text-sm font-semibold text-[color:var(--ink)] transition hover:bg-white"
              >
                Surprise me
              </button>
            </div>

            <div className="rounded-2xl border border-dashed border-[color:var(--stroke)] px-4 py-3 text-xs text-[color:var(--muted)]">
              {status === "loading" && "Ranking in progress..."}
              {status === "idle" && "Ready to query the ranker."}
              {status === "success" &&
                `Returned ${results.length} results${latency ? ` in ${latency}ms` : ""}.`}
              {status === "error" && (error ?? "Something went wrong.")}
            </div>
          </aside>

          <section className="flex flex-col gap-6">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-semibold">Ranked results</h2>
              <div className="pill rounded-full px-4 py-2 text-xs text-[color:var(--muted)]">
                {results.length > 0 ? `Top ${results.length}` : "No results yet"}
              </div>
            </div>

            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {results.map((movie) => (
                <article
                  key={movie.movie_id}
                  className="card flex flex-col overflow-hidden rounded-3xl"
                >
                  <div className="relative aspect-[2/3] w-full overflow-hidden">
                    <img
                      src={movie.poster_url || FALLBACK_POSTER}
                      alt={movie.title}
                      className="h-full w-full object-cover"
                    />
                  </div>
                  <div className="flex flex-1 flex-col gap-3 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="text-lg font-semibold leading-snug">
                        {movie.title}
                      </h3>
                      <span className="rounded-full bg-white/70 px-3 py-1 text-xs font-semibold text-[color:var(--accent-2)]">
                        {movie.score.toFixed(3)}
                      </span>
                    </div>
                    {movie.reasons && movie.reasons.length > 0 && (
                      <div className="flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.2em] text-[color:var(--muted)]">
                        {movie.reasons.slice(0, 3).map((reason) => (
                          <span key={reason} className="pill rounded-full px-3 py-1">
                            {reason.replaceAll("_", " ")}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </article>
              ))}
            </div>

            {status !== "loading" && results.length === 0 && (
              <div className="card rounded-3xl border border-dashed p-8 text-sm text-[color:var(--muted)]">
                Run a query to see ranked movies here. If you are getting errors,
                ensure the Go service is running and reachable at {apiBase}.
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
