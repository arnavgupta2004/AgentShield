# AgentShield

## One-line summary

AgentShield checks what an AI agent's *combination* of individually-allowed actions adds up to, and blocks it when nobody approved that combination — even though every single action was permitted.

## The Problem

AI agents take many actions per session — reading records, calling APIs, notifying people. Standard access control checks each action alone and approves all of them, since each really is fine by itself. But a *sequence* of allowed actions can combine into something nobody approved, without any single permission check ever being violated. That's a blind spot in per-action authorization itself — see the concrete examples below.

## What We Built

AgentShield evaluates an agent's *session* as a whole, not one call at a time. Given a declarative policy — which resource attributes make actions "sensitive together," and how much each recipient is cleared for — it graphs the session's calls, derives the combined capability, and checks it against policy before allowing it. Every decision returns a structured reason, never a black-box score. A working system: a 6-tool demo agent, two attack patterns, two honest baselines, a 30-session benchmark, a web UI, and a live AWS deployment.

## How It Works

1. **Observe agent actions** — each tool call becomes a node with attributes (resource, vendor, period, recipient).
2. **Build the session graph** — nodes are linked by an attribute policy declares significant (e.g. vendor identity).
3. **Derive the combined capability** — tally distinct policy-declared "compartments" among a call's linked ancestors.
4. **Evaluate against policy** — compare that count to the recipient's clearance threshold.
5. **Return an explainable ALLOW/BLOCK decision**, reasoning attached.

## Why It Is Different

| Approach | Checks | Result on our benchmark |
|---|---|---|
| Naive per-action | Is this one call allowed? | Misses both attacks (0/12) |
| Attack-specific rule ("Strong" baseline) | One hand-written rule for one pattern | Catches its pattern (6/6), misses another (0/6) |
| AgentShield | What does this *session* add up to? | Catches both (12/12), same engine, no per-attack code |

Generalization is **bounded by policy**: named combinations only, not undeclared risks.

## Two Demonstrated Attacks

**Attack 1 — cross-vendor pricing aggregation.** An agent reads pricing from two vendors, then sends both to a recipient cleared for only one vendor at a time. Blocked: 2 vendors present, threshold 1.

**Attack 2 — quarterly spend synthesis.** An agent reads one vendor's Q1–Q3 spend individually — each read is fine — then sends all three together, synthesizing most of a year's spend for a recipient cleared for only 2 quarters at once. Blocked under a *separate*, independently-declared conflict class, using the same function as Attack 1 — not special-cased code. Proof: a "vendor-only" policy in the same unmodified engine still blocks Attack 1 but no longer catches Attack 2 — the difference is entirely in policy.

## Evidence / Benchmark

30 sessions: 18 benign/near-miss, 12 attacks (6 of each pattern above).

| System | TP | FP | TN | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| Naive baseline | 0 | 0 | 18 | 12 | 1.00 | 0.00 | 0.00 |
| Strong baseline | 6 | 0 | 18 | 6 | 1.00 | 0.50 | 0.667 |
| **AgentShield** | **12** | **0** | **18** | **0** | **1.00** | **1.00** | **1.00** |

Backed by 37 automated tests, including false-positive probes built to break it. **Our own constructed benchmark** — not a real-world performance claim.

## AWS

Deployed as **API Gateway → AWS Lambda** (Python 3.12) in `ap-south-1`, running the identical engine used locally. Two DynamoDB tables are provisioned for policy and session-state data; **the Lambda does not read or write them at runtime** — it loads policy from the same bundled files as the local process. Lambda logs go to CloudWatch automatically; deployment is managed with AWS SAM.

We verified parity directly: all 30 benchmark sessions were sent to the live endpoint and diffed against local output — all 30 matched byte-for-byte. The frontend's "AWS Lambda (live)" option calls the deployed endpoint directly.

## What We Learned

1. **Per-action correctness doesn't imply session correctness.** Our naive baseline catches 0 of 12 attacks while approving every call.
2. **A well-built rule generalizes only as far as its author anticipated.** The Strong baseline is real and sensible; it still misses a shape it wasn't written for.
3. **Declarative detection makes generalization provable, not asserted.** The same engine catches both attacks, and fails one when its policy entry is removed.
4. **Local/cloud parity must be checked field-by-field.** We trust the deployment only because we diffed every response across all 30 sessions.

## Demo

The 3-minute demo shows, live: the naive baseline letting Attack 1 through; AgentShield blocking it with reasoning visible; the same session on the real AWS endpoint with the identical decision; the Strong baseline missing Attack 2 while AgentShield catches it; the same build missing Attack 2 after swapping to the vendor-only policy; and the benchmark table. Every decision comes from a real backend call, nothing simulated.

## Open Source / AI Tools

Built with Python/FastAPI, React + TypeScript (Vite), and AWS SAM. **Claude Code (Anthropic)** was used throughout as an AI coding assistant/agent — implementation, tests, an adversarial pre-deployment self-review that found and fixed a real (if narrow) bug before deployment, and this writeup — under the team's direction and review. No other AI coding tools were used.

## Future Work

Wiring the provisioned DynamoDB tables for real policy hot-reload and session-state persistence; an event-driven incremental architecture; CORS support for a public frontend; broader benchmark coverage.

## Team / Credits

Team AlphaBetaPi — WeMakeDevs "First Commit" (Bharat Build Tour), Sept 17–20, 2026.
