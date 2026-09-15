# Agent evaluation

Offline evaluation for the TripMind LangGraph travel agent using deterministic mock providers.

## Dataset

Five gold cases in `app/evaluation/dataset.py`:

1. Da Nang — 4 days
2. Hanoi — 3 days
3. Da Lat — 5 days
4. Phu Quoc — 4 days (with origin → flights required)
5. Hoi An — 2 days

## Metrics

| Metric | Meaning |
|--------|---------|
| Request understanding | Destination, dates, budget, travelers, preferences vs gold |
| Tool selection | Required tools called; forbidden tools (e.g. flights without origin) avoided |
| Itinerary validity | Day count, destination, validator checks, non-empty days |
| Budget validity | Estimated cost / breakdown within trip budget |
| Duplicate-free | No repeated `place_id` within the same day |
| Unsupported claims | Other-city catalog place names appearing in free-text response |
| Hallucination rate | Itinerary activities whose `place_id` is not in mock catalog/candidates |

## Run locally

```bash
cd backend
source .venv/bin/activate
python scripts/run_evaluation.py
```

JSON reports are written to:

- `evaluation/results/latest.json`
- `evaluation/results/eval_<timestamp>.json`

Update the regression baseline after intentional improvements:

```bash
python scripts/run_evaluation.py --save-baseline
```

Compare against the baseline (also used by pytest):

```bash
python scripts/run_evaluation.py --compare-baseline
pytest tests/test_evaluation_regression.py -q
```

Baseline file: `evaluation/baselines/latest.json`.
