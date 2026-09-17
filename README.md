# AgentShield

A working, evaluated, deterministic reference implementation of a defense
against **aggregation-inference in autonomous agent sessions**: cases
where an agent's individually-authorized tool calls, linked by shared
resource identity within a session, synthesize a combined result that
exceeds what the receiving principal is authorized for — even though no
single call, and no single recipient permission, was ever violated.

This is **not** a claim that AgentShield invented agent security, or
discovered a new vulnerability class, or that it automatically discovers
unknown security policies. The aggregation/inference problem is a
classical, decades-old access-control problem (database security
literature, the "mosaic effect" in classified-information handling),
recently re-formalized for multi-agent AI authorization and explicitly
noted as unsolved in deployed systems. AgentShield's contribution is a
working, tested, *evaluated* reference implementation of a defense
against this specific, well-scoped problem — not a discovery claim.

Built for WeMakeDevs "First Commit" (Sept 17–20, 2026), team AlphaBetaPi.

```
trajectory → resource linkage → compartment derivation →
derived capability → recipient clearance evaluation →
decision (ALLOW / BLOCK / ESCALATE) → explainable trace
```

The core decision engine is **deterministic and rule-based — no LLM, no
ML model, anywhere in the decision path.**

---

## 1. Repository structure

```
engine/       graph builder + deterministic decision algorithm (generic,
              zero attack/vendor/class-specific code — see engine/decision.py)
policy/       conflict_classes.yaml, clearances.yaml, tool_permissions.yaml
              (all human-readable policy DATA); policy/variants/vendor_only/
              is the restricted policy used in the §4c proof test and by
              the "same engine, before/after a policy edit" demo step
simulation/   the 6-tool mock AP/procurement agent / trajectory simulator
fixtures/     the 30-session benchmark set + Attack 1 / Attack 2 generators
baselines/    Naive (no cross-call state) and Strong (stateless Cedar-style
              point rule, deliberately missing the period-aware rule)
benchmark/    runner + metrics; benchmark/results/ holds real, committed
              output from an actual run (not fabricated)
api/          FastAPI backend: REST + WebSocket, zero authorization logic
              of its own — every endpoint calls into engine/baselines/benchmark
frontend/     React + Vite + TS: live session-graph demo + benchmark view
infra/        AWS SAM template + Lambda adapter over the same engine
tests/        unit + integration tests (37/37 passing — see §4 below)
```

## 2. Local run instructions

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

pytest -q                       # 37/37 tests
python -m benchmark.runner      # real 30-session benchmark run, prints JSON + summary

uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev -- --port 5173
```

Open `http://localhost:5173`. The Vite dev server proxies `/api` and
`/ws` to `http://127.0.0.1:8000` (see `frontend/vite.config.ts`), so run
the backend first.

## 3. AWS deployment instructions

See [infra/DEPLOY.md](infra/DEPLOY.md) for full `sam build` / `sam deploy`
/ invoke / teardown instructions, the architecture diagram, and an
explicit list of what's provisioned but intentionally not wired in this
build (EventBridge, DynamoDB-backed policy hot-reload). Not deployed to
a live AWS account from this environment — deploying is a billed,
account-affecting action left to you.

## 4. Test results (actual output)

```
$ pytest -q
.....................................                                    [100%]
37 passed, 2 warnings in 0.15s
```

(The 2 warnings are `starlette`/`httpx` deprecation notices from FastAPI's
`TestClient`, unrelated to correctness — see `tests/test_api_security.py`.)

Covering (per spec §9, plus a 2026-09-17 adversarial pre-deployment audit
— see §13): graph-builder linkage/tagging unit tests (`tests/test_graph.py`,
`tests/test_graph_adversarial.py`), decision-algorithm unit tests including
the ESCALATE margin band (`tests/test_decision.py`), the policy-data-not-code
proof (`tests/test_policy_data_not_code.py` — runs Attack 2 through the
*same* `engine.session_runner.run_session` function once with the
vendor-only policy [misses it] and once with the full policy [catches
it], plus a static check that `/engine/*.py` never names a specific
conflict class, vendor, or attack), a stronger genericity proof using a
structurally different, non-shipped conflict class
(`tests/test_third_conflict_class_generic_proof.py`), false-positive
probes (`tests/test_false_positives.py`), a fairness guard keeping
Baseline-Strong's hardcoded thresholds in sync with real policy
(`tests/test_baseline_strong_fairness.py`), API input-validation
regressions (`tests/test_api_security.py`), the Baseline-Strong
Attack-2-miss proof (`tests/test_baseline_strong_misses_attack2.py`), and the full
30-session integration run (`tests/test_benchmark_integration.py`).

## 5. Full 30-session benchmark results (actual numbers)

Real output from `python -m benchmark.runner`, committed at
[benchmark/results/results.json](benchmark/results/results.json) /
[summary.txt](benchmark/results/summary.txt):

| System | TP | FP | TN | FN | Precision | Recall | F1 | FPR (benign+near-miss) |
|---|---|---|---|---|---|---|---|---|
| Baseline-Naive | 0 | 0 | 18 | 12 | 1.00 | 0.00 | 0.00 | 0% |
| Baseline-Strong | 6 | 0 | 18 | 6 | 1.00 | 0.50 | 0.667 | 0% |
| **AgentShield** | **12** | **0** | **18** | **0** | **1.00** | **1.00** | **1.00** | **0%** |

## 6. Baseline comparison table — per-attack breakdown

| System | Attack 1 (6 sessions) | Attack 2 (6 sessions) |
|---|---|---|
| Baseline-Naive | 0/6 caught | 0/6 caught |
| Baseline-Strong | **6/6 caught** | **0/6 caught — genuine miss, not a bug** |
| AgentShield | 6/6 caught | 6/6 caught |

Baseline-Strong is a real, well-configured, single-rule (Cedar-style)
point evaluator — it has the cross-vendor-pricing rule and applies it
correctly. It has *no* notion of quarters/periods, so it structurally
cannot see Attack 2 (single-vendor, multi-quarter). That gap is the
entire point of the comparison: composable authorization requires
reasoning about the session graph, not just the current request.

18/18 benign + near-miss sessions ALLOW under every system (0% false
positives everywhere) — including the two sessions specifically designed
to test that AgentShield checks *recipient clearance*, not just raw
compartment overlap (`benign-high-clearance-*`, same 2-vendor pattern as
Attack 1 but routed to `finance_director`, who is cleared for it).

## 7. Architecture

```
                     ┌────────────────────────────┐
tool-call trajectory │ simulation/                │
 (fixtures/, or a    │ MockProcurementAgent        │  resolves payload_refs
 live agent's calls) │ .stream(specs)              │  (resource_id) into
                     └──────────────┬─────────────┘  session call_ids
                                    ▼
                     ┌────────────────────────────┐
                     │ engine/graph.SessionGraph   │  tags each node's
                     │  - add_call()                │  compartment_tags{}
                     │  - _linked() (shared vendor_id│  from policy-declared
                     │    / period)                  │  compartment_key lists
                     │  - ancestor_closure(sink)      │  (generic — no class
                     └──────────────┬─────────────┘  names in this file)
                                    ▼
                     ┌────────────────────────────┐
                     │ engine/decision.evaluate_call│  ONE function for every
                     │  sink? for each conflict     │  conflict class: count
                     │  class: count distinct        │  distinct members vs.
                     │  compartments vs. clearance   │  clearance[recipient][C]
                     └──────────────┬─────────────┘
                                    ▼
                     ┌────────────────────────────┐
                     │ engine/models.Trace          │  matched_conflict_class,
                     │  (explainable, structured)   │  member_compartments,
                     └──────────────┬─────────────┘  threshold, ancestor ids
                                    ▼
        ALLOW / BLOCK / ESCALATE + trace ──▶ api/ (REST + WS) ──▶ frontend/
```

`policy/*.yaml` is the only place conflict classes, compartment keys,
margins, and clearance thresholds are declared. `engine/` reads that
data through `engine/policy.py`'s typed `Policy` object and never
branches on a class/vendor/attack name — enforced by a static test (see
§4). Adding a new conflict class is a YAML edit; `baselines/` are
separate, simpler implementations used only for the comparison, not part
of AgentShield's own decision path.

## 8. Threat model

**Setting.** A 6-tool AP/procurement agent (`read_invoice`,
`read_purchase_order`, `search_vendor_db`, `update_vendor_record`,
`create_draft_payment`, `send_notification`) acting on behalf of a
finance team. Every individual tool call is authorized under standard
RBAC: any invoice in the processing queue may be read, any vendor may be
searched, and each recipient is a directory-verified principal legitimate
for the notifications/payments they receive.

**Attack 1 — cross-vendor pricing aggregation.** An agent reads invoices
and vendor records for two (or three) *different* vendors in one session,
then sends one notification bundling both to `alex_categorymgr`, who is
cleared to see pricing/terms data for only 1 vendor at a time
(`vendor_pricing_confidentiality` clearance = 1). Every call — read two
invoices, search two vendors, notify the correct recipient — is
individually authorized. The derived capability (a 2-vendor comparative
pricing synthesis) exceeds what the recipient is cleared for. →
**BLOCK**, `vendor_pricing_confidentiality`.

**Attack 2 — quarterly / near-annual spend synthesis.** Same shape, one
vendor, three (or four) distinct quarters (`annual_spend_synthesis`
clearance = 2 for `alex_categorymgr`). Reading Q1, Q2, Q3 invoices for
one vendor and notifying the category manager individually authorized
throughout; the synthesized near-annual spend picture is not. →
**BLOCK**, `annual_spend_synthesis`.

**What makes both attacks work against a naive system:** there is no
single tool call, and no single recipient-permission check, that is ever
violated. The unauthorized capability only exists at the level of *what
was synthesized across calls linked by shared resource identity within
the session* — which is exactly what `engine/graph.py`'s ancestor closure
and `engine/decision.py`'s per-class member count are built to catch,
generically, for any conflict class declared in policy.

## 9. Known limitations

- **Conflict classes are pre-declared policy data, not auto-discovered.**
  AgentShield reasons over compartments and thresholds an operator
  explicitly declared in `policy/conflict_classes.yaml` and
  `policy/clearances.yaml`. It does not detect unknown or undeclared
  aggregation risks — a class of information leakage nobody thought to
  encode a rule for will not be caught. This is inherent to the
  problem's classical formulation, not a shortcut taken here.
- This is a **reference implementation of a known, previously-unsolved-
  in-deployment problem**, evaluated against two concrete attack
  patterns and honest baselines — not a novel research discovery.
- `create_draft_payment`'s recipient/approver field is not part of the
  spec's literal tool signature (`create_draft_payment(vendor_id, amount,
  invoice_id)`); a draft payment needs *some* approving principal for
  clearance checks to mean anything, so `fixtures/sessions.py` routes it
  to `finance_director` by default. Flagged default, not a spec
  deviation the engine depends on — every benign fixture using it still
  passes ALLOW regardless of this choice.
- The AWS deployment provisions `PolicyTable` and `SessionGraphTable` but
  the bundled Lambda doesn't read/write them yet, and EventBridge isn't
  wired — see [infra/DEPLOY.md](infra/DEPLOY.md#known-limitations-of-this-build-read-before-assuming-production-readiness)
  for exactly what that means and what's needed to close the gap.
- `ESCALATE` (the configurable-margin band above a recipient's clearance
  threshold, before a hard BLOCK) is implemented and unit-tested
  (`tests/test_decision.py::test_margin_creates_an_escalate_band_before_block`)
  but every conflict class ships with `margin: 0` by default, so none of
  the 30 benchmark fixtures exercise it end-to-end — by design, since the
  spec's fixture labels are only ALLOW/BLOCK.
- No auth/accounts, no multi-tenancy — out of scope per spec §11/§15.

## 10. Recommended 3-minute demo flow

Supported directly by the frontend's Live Demo tab (fixture + system +
policy-variant selector) and Benchmark tab:

1. State the claim on screen (see the tagline in the app header).
2. Select an `attack1-*` fixture, system = **Baseline-Naive** → run →
   watch it ALLOW live.
3. Same fixture, system = **AgentShield** → run → BLOCK, trace + tally
   table shown (member compartments, count vs. threshold).
4. Select an `attack2-*` fixture, system = **Baseline-Strong** → run →
   ALLOWED (misses it) — narrate: a real, well-configured rule that
   simply was never given a quarter-aware conflict class.
5. Same fixture, system = **AgentShield**, policy = **full** → BLOCK.
   Switch policy to **vendor_only** and re-run the same fixture on
   AgentShield → ALLOW — same binary, only the policy file changed (see
   `policy/variants/vendor_only/`); zero lines of `engine/` differ
   (`tests/test_policy_data_not_code.py` proves this in CI).
6. Run a `benign-high-clearance-*` fixture live → correctly ALLOWED
   (same 2-vendor shape as Attack 1, but the recipient is cleared).
7. Switch to the Benchmark tab → show the 30-session comparison table
   and the Baseline-Strong Attack-2 row called out explicitly.
8. Brief flash of `infra/template.yaml`'s architecture, close.

## 11. Files created

Everything in this repository was created for this project — see
`git log` for the full commit-by-commit history. Top-level: `engine/`,
`policy/`, `simulation/`, `fixtures/`, `baselines/`, `benchmark/`,
`api/`, `frontend/`, `infra/`, `tests/`, plus root config
(`requirements.txt`, `pyproject.toml`, `.gitignore`, `.samignore`, this
README).

## 12. Remaining issues needing manual attention before the demo

- AWS stack has not been deployed (no credentials in this environment) —
  run `infra/DEPLOY.md`'s steps yourself before relying on a live URL
  for the demo; the local FastAPI + Vite path is fully verified and is
  the safer default for the recorded run-through.
- No CI workflow file is included (e.g. GitHub Actions running `pytest`
  on push) — worth adding before the submission deadline if judges will
  look for it, but was out of the strict build-priority order (spec
  §15) given the time available.
- Frontend UI is functional and was manually verified end-to-end in a
  real browser (live graph, edges, decision banner, compartment tally,
  benchmark table all confirmed against the real backend), but received
  no dedicated visual-polish pass per §15's deprioritization — a11y
  labeling, mobile layout, and animation are all unaddressed.

## 13. Pre-deployment audit (2026-09-17)

An adversarial audit was run against this repository before any AWS
deployment, explicitly trying to disprove the claims above rather than
confirm them. Full findings, severities, and reproduction commands are
below; nothing here was taken on faith — every claim was independently
re-derived from raw per-session output, not from the repo's own
aggregation code.

**Result: all 12 audit sections pass.** One genuine genericity gap was
found and fixed (not merely documented):

- **`engine/graph.py`'s coarse ancestor-linkage fallback was hardcoded to
  the Python attribute `vendor_id`** rather than being policy-declared.
  This never affected any benchmark outcome (compartment-bearing nodes
  are seeded directly via `payload_refs`, not via this fallback), but it
  was a real, if narrow, violation of "no domain concept hardcoded in
  `engine/`" — confirmed by first proving, empirically, that a naive
  fully-generic fallback (linking on *any* shared policy-keyed attribute)
  would introduce a false positive (two different vendors' invoices
  sharing only a quarter would wrongly merge into one ancestor closure).
  Fixed by moving the fallback attribute into policy data
  (`policy/conflict_classes.yaml`'s new `linkage_attribute: vendor_id`
  key, read by `engine/policy.py` into `Policy.linkage_attribute`) rather
  than widening it. All 30 benchmark outcomes are bit-identical before
  and after.
- Two API endpoints (`POST /api/sessions`, `POST /api/sessions/{id}/evaluate`)
  returned an unhandled 500 on invalid input (unknown tool name, unknown
  policy variant) instead of a 400 — fixed in `api/main.py`; regression
  tests in `tests/test_api_security.py`.
- The WebSocket's client-supplied `delay_ms` had no upper bound — clamped
  to 5000ms in `api/main.py`.
- Baseline-Strong's docstring imprecisely called itself fully "stateless"
  while it does accumulate a resource→vendor lookup across a session's
  calls; reworded for accuracy in `baselines/strong.py` (its threshold
  values were already exactly the real `policy/clearances.yaml` numbers,
  now pinned by a regression test in `tests/test_baseline_strong_fairness.py`).

No other violations were found: no attack/vendor/class names anywhere in
`engine/`, no randomness/timestamps/UUIDs anywhere in the decision path,
byte-for-byte identical benchmark output across repeated clean runs, the
local API and the AWS Lambda adapter produce byte-identical decisions and
traces for all 30 fixtures (confirmed via literal function-object
identity, not just equal output), and the frontend never sets a decision
value from anything but a real backend response. See the conversation
this audit was run in for the full per-section report (A–F); the
short version:

| Section | Result |
|---|---|
| 1. Benchmark re-verified from scratch | PASS — confusion matrices match exactly (see §5/§6 above) |
| 2. No attack-specific code in `engine/` | PASS (after the `linkage_attribute` fix) |
| 3. Policy-data-vs-code, third synthetic class | PASS — provenance-keyed class detected correctly, zero `engine/*.py` bytes changed |
| 4. Baseline-Strong fairness | PASS — real thresholds, plausible single-rule scope, now regression-tested |
| 5. False positives | PASS — 6 new adversarial scenarios added, all correctly ALLOW |
| 6. Graph logic | PASS — 5 new adversarial scenarios added (duplicates, ordering, session isolation, dangling refs, post-sink calls) |
| 7. AWS/local engine parity | PASS — literal function identity + byte-identical output on all 30 fixtures |
| 8. Reproducibility | PASS — 3x clean reruns of tests and benchmark, byte-identical |
| 9. Frontend honesty | PASS — no client-side decision fabrication found |
| 10. Security review | 2 input-validation bugs fixed, CORS/no-auth documented as demo-scope, no secrets/unsafe YAML/injection found |
| 11. README truth audit | Stale test count corrected; no overclaiming found |
| 12. Deployment readiness | Ready for `sam deploy` at your discretion — nothing deployed from here |

**Reproduce it yourself:**

```bash
rm -rf benchmark/results .pytest_cache && find . -name __pycache__ -not -path "./.venv/*" -not -path "./frontend/*" -exec rm -rf {} +
source .venv/bin/activate
pytest -q                              # 37/37
python -m benchmark.runner > benchmark/results/results.json 2> benchmark/results/summary.txt
cat benchmark/results/summary.txt      # matches §5 above exactly
```
