#!/usr/bin/env python3
"""Cross-provider model lookup for the which-model skill. Standard library only; run with python3 -I.

Pulls three aggregator catalogs into one in-memory table of deployments (provider x model)
and prints it. Nothing is written except the raw download cache.

  list     filter, rank and print deployments
  hosts    every provider serving one model, cheapest first
  show     one deployment vertically, non-empty fields only
  sources  which catalogs answered, how old the cache is
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SOURCES = {
    # models.dev is the breadth spine: ~235 providers, ~9k deployments, no key.
    "models.dev": {"url": "https://models.dev/api.json"},
    # OpenRouter adds cached-input price, per-model max output and retirement dates.
    "openrouter": {"url": "https://openrouter.ai/api/v1/models"},
    # Artificial Analysis is the only quality/speed signal. Free tier, fewer fields.
    "aa": {
        "url": "https://artificialanalysis.ai/api/v2/language/models/free",
        "pro_url": "https://artificialanalysis.ai/api/v2/language/models",
        "env": "AA_API_KEY",
        "header": "x-api-key",
        "optional": True,
    },
}

CACHE_TTL_H = 12
UA = "which-model-skill/1 (+stdlib urllib)"
STATUS: dict[str, str] = {}

FIELDS = [
    "ref", "provider", "model_id", "name", "family", "open_weights",
    "context", "max_output", "price_in", "price_out", "price_cache_read",
    "modalities", "tools", "reasoning", "release", "expiry",
    "aa_intelligence", "aa_coding", "aa_agentic", "aa_tps", "aa_ttft", "aa_variant", "catalogs",
]

SORTS = {
    "cost": ("cost", False), "in": ("price_in", False), "out": ("price_out", False),
    "context": ("context", True), "output": ("max_output", True),
    "intelligence": ("aa_intelligence", True), "coding": ("aa_coding", True),
    "agentic": ("aa_agentic", True), "speed": ("aa_tps", True), "ttft": ("aa_ttft", False),
    "release": ("release", True), "ref": ("ref", False),
}


def die(msg: str, code: int = 1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def norm(s) -> str:
    """Fold a model name or id to its comparable core: 'Kimi K2 (0905)' -> 'kimik20905'."""
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def num(x):
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if f < 0 else f


# ---------------------------------------------------------------- fetching

def cache_dir(arg) -> Path:
    p = Path(arg) if arg else Path(os.environ.get("TMPDIR", "/tmp")) / "which-model"
    p.mkdir(parents=True, exist_ok=True)
    return p


def fetch_json(url: str, key: str, header: str, timeout: int):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    if key:
        req.add_header(header, key)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_paged(url: str, key: str, header: str, timeout: int):
    """AA returns 200 models a page; walk them all into one {..., data: [...]} blob."""
    first = fetch_json(url, key, header, timeout)
    pag = first.get("pagination") if isinstance(first, dict) else None
    if not pag or not pag.get("has_more"):
        return first
    sep = "&" if "?" in url else "?"
    for page in range(2, int(pag.get("total_pages") or 1) + 1):
        nxt = fetch_json(f"{url}{sep}page={page}", key, header, timeout)
        first["data"].extend(nxt.get("data") or [])
    first["pagination"] = {"pages_merged": pag.get("total_pages")}
    return first


def get(name: str, cdir: Path, refresh: bool, timeout: int):
    """Return parsed JSON for one source, or None. Caches raw bytes for CACHE_TTL_H."""
    spec = SOURCES[name]
    blob = cdir / f"{name}.json"
    if not refresh and blob.exists():
        age_h = (time.time() - blob.stat().st_mtime) / 3600
        if age_h < CACHE_TTL_H:
            try:
                data = json.loads(blob.read_text(encoding="utf-8"))
                STATUS[name] = f"cache {age_h:.1f}h old"
                return data
            except json.JSONDecodeError:
                pass

    key = os.environ.get(spec["env"], "") if spec.get("env") else ""
    if spec.get("env") and not key:
        STATUS[name] = f"skipped, {spec['env']} not set"
        return None

    last = ""
    for url in [spec["url"]] + ([spec["pro_url"]] if spec.get("pro_url") else []):
        try:
            data = fetch_paged(url, key, spec.get("header", "Authorization"), timeout)
            raw = json.dumps(data).encode("utf-8")
            blob.write_bytes(raw)
            STATUS[name] = f"fetched {len(raw) // 1024} KB"
            return data
        except urllib.error.HTTPError as e:
            body = e.read()[:200].decode("utf-8", "replace")
            last = f"HTTP {e.code} {body.strip()}"
        except Exception as e:  # network, DNS, timeout, bad JSON
            last = f"{type(e).__name__}: {e}"

    STATUS[name] = f"failed, {last}"
    if blob.exists():  # stale beats nothing
        try:
            data = json.loads(blob.read_text(encoding="utf-8"))
            age_h = (time.time() - blob.stat().st_mtime) / 3600
            STATUS[name] += f" (using stale cache {age_h:.1f}h old)"
            return data
        except json.JSONDecodeError:
            pass
    return None


# ---------------------------------------------------------------- parsing

def row(**kw):
    r = {f: None for f in FIELDS}
    r["catalogs"] = []
    r.update(kw)
    return r


def from_models_dev(data) -> dict:
    """{providerId: {models: {modelId: {...}}}} -> rows keyed by 'provider/model_id'."""
    rows = {}
    for pid, p in (data or {}).items():
        if not isinstance(p, dict):
            continue
        for mid, m in (p.get("models") or {}).items():
            cost, limit = m.get("cost") or {}, m.get("limit") or {}
            mods = (m.get("modalities") or {}).get("input") or []
            ref = f"{pid}/{mid}"
            rows[ref] = row(
                ref=ref, provider=pid, model_id=mid,
                name=m.get("name") or mid, family=m.get("family"),
                open_weights=m.get("open_weights"),
                context=num(limit.get("context")), max_output=num(limit.get("output")),
                price_in=num(cost.get("input")), price_out=num(cost.get("output")),
                price_cache_read=num(cost.get("cache_read")),
                modalities=";".join(mods) if mods else None,
                tools=m.get("tool_call"), reasoning=m.get("reasoning"),
                release=m.get("release_date"), catalogs=["models.dev"],
            )
    return rows


def from_openrouter(data) -> dict:
    """OpenRouter's own routing layer, one row per model id."""
    rows = {}
    for m in (data or {}).get("data", []):
        mid = m.get("id")
        if not mid:
            continue
        pricing, top = m.get("pricing") or {}, m.get("top_provider") or {}
        params = m.get("supported_parameters") or []
        mods = (m.get("architecture") or {}).get("input_modalities") or []
        per_m = lambda v: None if num(v) is None else num(v) * 1_000_000
        ref = f"openrouter/{mid}"
        # OpenRouter prefixes the vendor ("MoonshotAI: Kimi K2.6"); strip it so names
        # line up with models.dev and Artificial Analysis.
        name = re.sub(r"^[^:]{1,20}:\s*", "", m.get("name") or mid)
        rows[ref] = row(
            ref=ref, provider="openrouter", model_id=mid,
            name=name, family=mid.split("/")[0],
            context=num(m.get("context_length")),
            max_output=num(top.get("max_completion_tokens")),
            price_in=per_m(pricing.get("prompt")), price_out=per_m(pricing.get("completion")),
            price_cache_read=per_m(pricing.get("input_cache_read")),
            modalities=";".join(mods) if mods else None,
            tools="tools" in params, reasoning="reasoning" in params,
            release=dt.date.fromtimestamp(m["created"]).isoformat() if m.get("created") else None,
            expiry=m.get("expiration_date"), catalogs=["openrouter"],
        )
    return rows


# AA publishes one entry per reasoning-effort variant: "Kimi K2.6 (Reasoning)", "GPT-6 Sol (Low)".
VARIANT_RE = re.compile(r"-(non-reasoning|reasoning|thinking|xhigh|high|medium|minimal|low)$")


def aa_index(data) -> dict:
    """Normalised name/slug -> quality and speed figures. Best variant wins a collision."""
    items = data if isinstance(data, list) else (data or {}).get("data") or []
    idx = {}
    for m in items:
        if not isinstance(m, dict):
            continue
        ev, perf = m.get("evaluations") or {}, m.get("performance") or {}
        pick = lambda *names: next(
            (num(src[n]) for src in (ev, perf, m) for n in names
             if isinstance(src, dict) and src.get(n) is not None),
            None,
        )
        entry = {
            "aa_intelligence": pick("artificial_analysis_intelligence_index", "intelligence_index"),
            "aa_coding": pick("artificial_analysis_coding_index", "coding_index"),
            "aa_agentic": pick("artificial_analysis_agentic_index", "agentic_index"),
            "aa_tps": pick("median_output_tokens_per_second", "output_tokens_per_second"),
            "aa_ttft": pick("median_time_to_first_token_seconds", "time_to_first_token_seconds"),
            "aa_variant": m.get("name"),
        }
        if not any(entry[k] is not None for k in entry if k != "aa_variant"):
            continue

        # Richer entry wins, then the higher-scoring variant.
        rank = (sum(entry[k] is not None for k in entry if k != "aa_variant"),
                entry["aa_intelligence"] or -1, entry["aa_tps"] or -1)
        slug = str(m.get("slug") or "")
        keys = {slug, VARIANT_RE.sub("", slug), re.sub(r"\s*\(.*?\)\s*", "", str(m.get("name") or ""))}
        for k in keys:
            k = norm(k)
            if k and rank > idx.get(k, (None, (-1, -1, -1)))[1]:
                idx[k] = (entry, rank)
    return {k: v[0] for k, v in idx.items()}


def build(cdir: Path, refresh: bool, timeout: int) -> list[dict]:
    rows = from_models_dev(get("models.dev", cdir, refresh, timeout))
    for ref, r in from_openrouter(get("openrouter", cdir, refresh, timeout)).items():
        if ref in rows:  # models.dev also lists openrouter; OpenRouter's own feed wins on price
            for f in FIELDS:
                if r.get(f) is not None and f != "catalogs":
                    rows[ref][f] = r[f]
            rows[ref]["catalogs"].append("openrouter")
        else:
            rows[ref] = r

    idx = aa_index(get("aa", cdir, refresh, timeout))
    if idx:
        for r in rows.values():
            hit = idx.get(norm(r["name"])) or idx.get(norm(r["model_id"].split("/")[-1]))
            if hit:
                r.update(hit)
                r["catalogs"].append("aa")
    return list(rows.values())


# ---------------------------------------------------------------- cost, filters, output

def cost_per_1k(r, tin: float, tout: float, hit: float):
    """$ per 1,000 calls at the given workload. Cache-read price falls back to input price."""
    pin, pout = r["price_in"], r["price_out"]
    if pin is None or pout is None:
        return None
    cached = r["price_cache_read"] if r["price_cache_read"] is not None else pin
    per_call = (tin * (1 - hit) * pin + tin * hit * cached + tout * pout) / 1_000_000
    return per_call * 1000


def tri(v):
    return "" if v is None else ("y" if v else "n")


def select(rows, a) -> list[dict]:
    q = [norm(x) for x in (a.q or [])]
    out = []
    for r in rows:
        hay = norm(f"{r['ref']} {r['name']} {r['family'] or ''}")
        if q and not all(t in hay for t in q):
            continue
        if a.provider and r["provider"] not in a.provider:
            continue
        if a.not_provider and r["provider"] in a.not_provider:
            continue
        if a.open and r["open_weights"] is not True:
            continue
        if a.closed and r["open_weights"] is not False:
            continue
        if a.tools and r["tools"] is not True:
            continue
        if a.image and "image" not in (r["modalities"] or ""):
            continue
        if a.reasoning and r["reasoning"] is not True:
            continue
        if a.min_context and (r["context"] or 0) < a.min_context:
            continue
        if a.min_output and (r["max_output"] or 0) < a.min_output:
            continue
        if a.max_in is not None and (r["price_in"] is None or r["price_in"] > a.max_in):
            continue
        if a.max_out is not None and (r["price_out"] is None or r["price_out"] > a.max_out):
            continue
        if a.no_free and not (r["price_in"] or r["price_out"]):
            continue
        if a.since and (r["release"] or "") < a.since:
            continue
        if a.min_score is not None and (r[f"aa_{a.score}"] or -1) < a.min_score:
            continue
        r["cost"] = cost_per_1k(r, a.in_tokens, a.out_tokens, a.cache_hit)
        out.append(r)

    # Rank on the sort key, with unknowns last rather than treated as zero.
    key, rev = SORTS[a.sort]
    numeric = key not in ("release", "ref")
    known = [r for r in out if r.get(key) not in (None, "")]
    unknown = [r for r in out if r.get(key) in (None, "")]
    known.sort(key=lambda r: num(r[key]) if numeric else str(r[key]), reverse=rev)
    out = known + unknown
    return out[: a.limit] if a.limit else out


def money(v, places=3):
    return "" if v is None else f"{v:,.{places}f}"


def table(rows, a):
    cols = [
        ("ref", "ref", lambda r: r["ref"]),
        ("$/1k", ">", lambda r: money(r.get("cost"), 2)),
        ("in", ">", lambda r: money(r["price_in"])),
        ("out", ">", lambda r: money(r["price_out"])),
        ("cache", ">", lambda r: money(r["price_cache_read"])),
        ("ctx", ">", lambda r: f"{int(r['context']):,}" if r["context"] else ""),
        ("maxout", ">", lambda r: f"{int(r['max_output']):,}" if r["max_output"] else ""),
        ("ow", ">", lambda r: tri(r["open_weights"])),
        ("tool", ">", lambda r: tri(r["tools"])),
        ("img", ">", lambda r: "y" if "image" in (r["modalities"] or "") else ""),
        ("intl", ">", lambda r: money(r["aa_intelligence"], 1)),
        ("code", ">", lambda r: money(r["aa_coding"], 1)),
        ("tps", ">", lambda r: money(r["aa_tps"], 0)),
        ("released", "ref", lambda r: r["release"] or ""),
    ]
    body = [[f(r) for _, _, f in cols] for r in rows]
    heads = [h for h, _, _ in cols]
    w = [max(len(heads[i]), *(len(b[i]) for b in body)) if body else len(heads[i]) for i in range(len(cols))]
    just = lambda i, s: s.ljust(w[i]) if cols[i][1] == "ref" else s.rjust(w[i])
    print("  ".join(just(i, heads[i]) for i in range(len(cols))))
    print("  ".join("-" * w[i] for i in range(len(cols))))
    for b in body:
        print("  ".join(just(i, b[i]) for i in range(len(b))))
    print(f"\n{len(rows)} deployment(s). $/1k = {a.in_tokens:,.0f} in ({a.cache_hit:.0%} cached) "
          f"+ {a.out_tokens:,.0f} out, x1000 calls. Prices $/1M tokens.")
    note = [f"{k}: {v}" for k, v in STATUS.items() if "failed" in v or "skipped" in v]
    if note:
        print("incomplete -> " + "; ".join(note))


def emit(rows, a):
    if a.json:
        print(json.dumps(rows, indent=1, default=str))
        return
    table(rows, a)
    key = SORTS[a.sort][0]
    if key.startswith("aa_") and not any(r[key] is not None for r in rows):
        print(f"warning: no row has {key}; this ranking is arbitrary. Run `sources` for coverage.")


# ---------------------------------------------------------------- commands

def cmd_list(rows, a):
    emit(select(rows, a), a)


def cmd_hosts(rows, a):
    a.q = a.q or [a.model]
    sel = select(rows, a)
    if not sel:
        die(f"nothing matches {a.model!r}; widen the query or run `sources`", 3)
    names = {}
    for r in sel:
        names.setdefault(norm(r["name"]), []).append(r)
    emit(sel, a)
    if not a.json:
        print(f"{len(names)} distinct model name(s) across {len({r['provider'] for r in sel})} provider(s).")
        priced = [r["cost"] for r in sel if r.get("cost") is not None]
        if len(priced) > 1:
            print(f"cost spread: {min(priced):,.2f} - {max(priced):,.2f} $/1k calls "
                  f"({max(priced) / min(priced):.1f}x) — confirm the cheap end on the provider's own page.")


def cmd_show(rows, a):
    hits = [r for r in rows if r["ref"] == a.ref] or \
           [r for r in rows if norm(a.ref) in norm(r["ref"])]
    if not hits:
        die(f"no deployment matches {a.ref!r}", 3)
    for r in hits[:5]:
        r["cost"] = cost_per_1k(r, a.in_tokens, a.out_tokens, a.cache_hit)
        print(f"\n=== {r['ref']}")
        for f in FIELDS + ["cost"]:
            v = r.get(f)
            if v is None or v == [] or v == "":
                continue
            if isinstance(v, list):
                v = ";".join(v)
            elif isinstance(v, float) and v.is_integer():
                v = f"{int(v):,}"
            print(f"  {f:<18} {v}")
        sib = [o for o in rows if norm(o["name"]) == norm(r["name"]) and o["ref"] != r["ref"]]
        if sib:
            print(f"  {'other_hosts':<18} {len(sib)}: " + ", ".join(sorted({o['provider'] for o in sib})[:12]))
    if len(hits) > 5:
        print(f"\n... {len(hits) - 5} more match; narrow the ref.")


def cmd_sources(rows, a):
    for name in SOURCES:
        print(f"{name:<12} {STATUS.get(name, 'not reached')}")
    print(f"\n{len(rows)} deployments, {len({r['provider'] for r in rows})} providers.")
    print("score coverage: " + ", ".join(
        f"{c}={sum(1 for r in rows if r[f'aa_{c}'] is not None)}"
        for c in ("intelligence", "coding", "agentic", "tps")))
    aa = STATUS.get("aa", "not reached")
    if aa.startswith(("failed", "skipped", "not reached")):
        print(f"No quality or speed signal at all (aa {aa}).")
    elif not any(r["aa_coding"] is not None for r in rows):
        print("AA's free tier fills intelligence and speed only; coding and agentic stay null.")
    print("Where a score is missing, rank on price and capability here, then take quality for the "
          "shortlist from a leaderboard by hand.")


# ---------------------------------------------------------------- cli

def main(argv=None):
    p = argparse.ArgumentParser(prog="sweep.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cache", help="download cache dir (default $TMPDIR/which-model)")
    p.add_argument("--refresh", action="store_true", help=f"re-download even if cache < {CACHE_TTL_H}h old")
    p.add_argument("--timeout", type=int, default=45)
    p.add_argument("--json", action="store_true", help="emit rows as JSON instead of a table")

    def common(sp):
        sp.add_argument("--q", nargs="+", metavar="TERM", help="all terms must appear in ref/name/family")
        sp.add_argument("--provider", nargs="+")
        sp.add_argument("--not-provider", nargs="+")
        sp.add_argument("--open", action="store_true", help="open-weights only")
        sp.add_argument("--closed", action="store_true", help="closed-weights only")
        sp.add_argument("--tools", action="store_true")
        sp.add_argument("--image", action="store_true")
        sp.add_argument("--reasoning", action="store_true")
        sp.add_argument("--min-context", type=int, default=0)
        sp.add_argument("--min-output", type=int, default=0)
        sp.add_argument("--max-in", type=float, help="max $/1M input")
        sp.add_argument("--max-out", type=float, help="max $/1M output")
        sp.add_argument("--no-free", action="store_true",
                        help="drop $0 rows (free tiers, plan-priced hosts)")
        sp.add_argument("--since", metavar="YYYY-MM-DD", help="released on or after")
        sp.add_argument("--score", choices=["intelligence", "coding", "agentic"], default="intelligence")
        sp.add_argument("--min-score", type=float)
        sp.add_argument("--sort", choices=sorted(SORTS), default="cost")
        sp.add_argument("--limit", type=int, default=25)
        sp.add_argument("--in-tokens", type=float, default=10000)
        sp.add_argument("--out-tokens", type=float, default=1000)
        sp.add_argument("--cache-hit", type=float, default=0.0, help="0-1 share of input served from cache")

    sub = p.add_subparsers(dest="cmd", required=True)
    common(sub.add_parser("list", help="filter, rank and print deployments"))
    h = sub.add_parser("hosts", help="every provider serving one model, cheapest first")
    h.add_argument("model")
    common(h)
    h.set_defaults(limit=0)
    s = sub.add_parser("show", help="one deployment vertically")
    s.add_argument("ref")
    common(s)
    common(sub.add_parser("sources", help="catalog status and cache age"))

    a = p.parse_args(argv)
    if a.open and a.closed:
        die("--open and --closed are mutually exclusive")
    if not 0 <= a.cache_hit <= 1:
        die("--cache-hit must be between 0 and 1")

    rows = build(cache_dir(a.cache), a.refresh, a.timeout)
    if not rows:
        print("\n".join(f"{k}: {v}" for k, v in STATUS.items()), file=sys.stderr)
        die("no catalog reached; treat the market as unswept", 2)

    {"list": cmd_list, "hosts": cmd_hosts, "show": cmd_show, "sources": cmd_sources}[a.cmd](rows, a)


if __name__ == "__main__":
    main()
