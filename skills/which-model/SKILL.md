---
name: which-model
description: >-
  Answer "which model should I use for this?" by sweeping ~9,000 deployments
  across ~235 providers (models.dev + OpenRouter + Artificial Analysis), ranking
  on real cost and capability, then confirming the finalists at the source. Use
  to pick a model for a task, fill model settings in an app/agent/gateway
  config, survey what a capability or price point buys, or find who else serves
  a model you already use and for how much.
metadata:
  openclaw:
    requires:
      bins: [python3]
    envVars:
      - name: AA_API_KEY
        required: false
---

# Which model

Three aggregator catalogs merge into one table. Filter it, shortlist two or three finalists, confirm them at the source, answer.

```bash
python3 -I $SKILL/scripts/sweep.py <list|hosts|show|sources> [filters]
```

Downloads cache for 12 hours in `$TMPDIR/which-model`; add `--refresh` to force. Every command rebuilds the table, so the first call of a session takes a few seconds.

## Step 1: Pin the question

Get these four before sweeping. Ask only what the user hasn't said; infer the rest from their code or config and state what you inferred.

- **Task** — what the model does, and what "good" means for it.
- **Hard limits** — context, tool calling, image input, open weights, providers or regions allowed or banned, data retention.
- **Workload** — tokens in and out per call, and the cached share of input. No idea → use the `10000 / 1000 / 0` default and say so; a wrong workload reorders the whole table.
- **Target** — just a recommendation, or a config to fill in? If a config, read it first: its ref syntax and supported providers are a hard filter.

One sentence back confirming all four, then sweep. Don't interrogate; a single round is usually enough.

## Step 2: Sweep

```bash
python3 -I $SKILL/scripts/sweep.py list --tools --min-context 200000 --open \
  --in-tokens 30000 --out-tokens 1500 --cache-hit 0.8 --sort cost --limit 20
```

`list` ranks deployments; `--q` takes substrings matched against ref, name and family. Filters: `--provider`, `--not-provider`, `--open` / `--closed`, `--tools`, `--image`, `--reasoning`, `--min-context`, `--min-output`, `--max-in`, `--max-out`, `--since`, `--min-score`, `--no-free` (drops $0 rows), `--limit`, `--json`. Sort by `cost` (default), `in`, `out`, `context`, `output`, `intelligence`, `coding`, `agentic`, `speed`, `ttft`, `release`, `ref`.

`$/1k` is the ranking column: cost per 1,000 calls at your workload, cached input priced at `price_cache_read` and falling back to input price when the host publishes none. Per-token prices mislead whenever the input/output ratio or cache hit rate is lopsided, so set `--in-tokens`, `--out-tokens` and `--cache-hit` before reading the order.

| Catalog | Key | What it carries |
|---|---|---|
| models.dev | none | the breadth: ~235 providers, ~9,000 deployments, price, limits, modalities, tool calling, open weights, release date |
| OpenRouter | none | its own routing layer with cached-input price, per-model max output, retirement dates |
| Artificial Analysis | `AA_API_KEY` (free) | the only quality and speed signal: intelligence index, median tokens/s, TTFT |

**AA's free tier fills intelligence and speed only — `coding` and `agentic` come back null, and roughly a quarter of entries have an intelligence index at all.** `sort` on an all-empty column warns you. AA also publishes one entry per reasoning-effort variant ("Kimi K2.6 (Reasoning)"); the table keeps the best-scoring variant and names it in `aa_variant`, so the score may not describe the effort level you'll run at. Treat every AA number as triage-grade: it is per model, not per host or precision.

Run `sources` whenever a column looks empty. It prints each catalog's status, cache age, and score coverage. Stale cache is used when a fetch fails and says so; no catalog at all exits 2 — report the market as unswept rather than guessing.

## Step 3: Compare hosts

The same open-weights model varies several-fold in price, context and max output across hosts:

```bash
python3 -I $SKILL/scripts/sweep.py hosts kimi-k2.6 --no-free
```

It prints every deployment of the match, cheapest first, and the cost spread. `show <ref>` gives one deployment vertically plus how many other providers serve the same model.

Price alone doesn't decide it. The cheap end of a spread is usually cheap for a reason — aggressive quantization, a short served context, a low max output, a free tier with no availability promise, or promotional pricing. Shortlist 2–3, not 1.

## Step 4: Confirm the finalists

Catalog data is second-hand and goes stale. Before recommending, check each finalist on the provider's own model page, and say which page you used:

- **Price**, including cached input, and whether it's promotional or list.
- **Precision** — how *this host* quantized the weights. Unpublished is a finding; don't guess. Sub-4-bit is disqualifying for most work.
- **Served context and max output**, which are often below the model's native window.
- **Deprecation** — retirement date, and whether the ref is a pinned snapshot or a floating tag.
- **Data handling and rate limits** for the tier the user is actually on.

Quality beyond AA's intelligence index: check a leaderboard for the task, not a general index. SWE-bench for coding, BFCL or equivalent for tool calling. Anything unconfirmed stays an open item.

## Step 5: Answer

Lead with the pick and one sentence of why. Then:

- A short table: chosen model, `$/1k` at the stated workload, context, the runner-up, and what the runner-up would get you.
- The deciding trade-off, named in plain words.
- Assumptions you made about workload or constraints, and anything you couldn't confirm.
- For a config target: the exact ref string in that system's syntax, plus a fallback, then the diff. Confirm before writing to a live system.

Re-run the sweep next time rather than trusting this answer's prices.
