# Multi-agent roles

Each agent exists only when it has a clear job. No filler agents.

| Agent | Why it exists | When the supervisor calls it |
|-------|---------------|------------------------------|
| **Supervisor** | Understand the request, decide required specialists, enforce loop/timeout/fallback | Always — after bootstrap and after every specialist returns |
| **Flight** | Search + rank flights | Only when `origin` is present (otherwise skipped) |
| **Hotel** | Search + rank lodging | Always for a valid trip window |
| **Place** | Attractions + restaurants catalog | Always — itinerary needs grounded place ids |
| **Weather** | Per-day forecast for the stay | Always — validation and optimization need it |
| **Itinerary** | Build day-by-day schedule from catalogs | After Place (+ Weather); needs candidates first |
| **Budget** | Cost breakdown + swaps (BudgetAgent / ItineraryOptimizer) | After Itinerary — food/activity/transport lines require a schedule |
| **Validation** | Detect invalid plans (unknown ids, duplicates, budget, weather) | After Budget — final gate before finalize |

## Not separate agents (on purpose)

- **Parse / memory / RAG knowledge** stay on the supervisor bootstrap path. They are cross-cutting context, not domain specialists.
- **Finalize / update_memory** are terminal sinks, not planners.

## Execution order vs naive Budget-before-Itinerary

A diagram that places Budget before Itinerary is useful for *envelope* thinking, but full cost analysis needs a schedule. TripMind therefore:

1. ranks flights/hotels early (Flight / Hotel agents)
2. builds the schedule (Itinerary)
3. runs Budget on that schedule using the ranked offers
4. validates

## Loop safety

- `max_iterations` (default 16)
- monotonic `deadline_ts` timeout (default 45s)
- per-agent try/except → record `agent_errors`, continue with empty/partial data
- one repair re-queue if itinerary is missing after the first itinerary pass
- `fallback` node → best-effort finalize when timeout/iterations fire
