# AWS deployment

Cost-conscious "Ship It" architecture (spec section 8): API Gateway ->
Lambda -> DynamoDB, CloudWatch for the audit log. No SageMaker, no
Bedrock, no per-token service -- the decision path is deterministic
Python, so it needs none.

```
API Gateway --(POST /sessions/{id}/evaluate)--> Lambda (engine/session_runner.run_session)
                                                    |
                                                    +--> CloudWatch Logs (decision/audit trail)

DynamoDB: PolicyTable (conflict classes + clearances), SessionGraphTable (per-session graph state)
```

## Prerequisites

- AWS SAM CLI (`brew install aws-sam-cli` or see AWS docs)
- An AWS account with credentials configured (`aws configure`)

## Deploy

```bash
cd infra
sam build
sam deploy --guided
```

`sam deploy --guided` will prompt for a stack name, region, and confirm
IAM role creation; it writes your answers to `samconfig.toml` for
repeat deploys (`sam deploy` without `--guided` after the first run).

## Invoke

```bash
curl -X POST "$(aws cloudformation describe-stacks \
    --stack-name <your-stack-name> \
    --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)sessions/demo-1/evaluate" \
  -H "Content-Type: application/json" \
  -d '{
        "session_id": "demo-1",
        "calls": [
          {"tool": "read_invoice", "resource_id": "inv_1", "vendor_id": "V_Acme", "period": "Q1"},
          {"tool": "read_invoice", "resource_id": "inv_2", "vendor_id": "V_Boreal", "period": "Q1"},
          {"tool": "send_notification", "resource_id": "n1", "vendor_id": "V_Acme",
           "recipient": "alex_categorymgr", "payload_refs": ["inv_1", "inv_2"]}
        ]
      }'
```

## Smoke test after deploy (or any time, to recheck a live deployment)

`infra/smoke_test.py` hits the real deployed API with real fixtures from
`fixtures/sessions.py` (never invented payloads) and checks the response
against both the fixture's own expected label AND the local engine's live
output for the identical input -- so it catches both "the deployment
disagrees with the benchmark" and "the deployment is running a stale
build" regressions. No AWS credentials needed -- it's a plain HTTPS
client hitting the public API Gateway URL, same as any caller.

```bash
source .venv/bin/activate
python infra/smoke_test.py --url https://<api-id>.execute-api.<region>.amazonaws.com/prod
python infra/smoke_test.py --url ... --all     # all 30 fixtures instead of the default 6
```

Exit code is non-zero on any mismatch, so it's safe to script/CI later.
Verified 2026-09-17 against the `ap-south-1` deployment: 30/30 fixtures
match both the fixture's expected label and the local engine's live
output, byte-for-byte on decision and matched conflict class.

## Teardown

```bash
sam delete --stack-name <your-stack-name>
```

## Known limitations of this build (read before assuming production-readiness)

This hackathon build deliberately does **not** wire two pieces of the
architecture all the way through, in the same spirit as spec section 8's
explicit instruction not to fake an EventBridge integration that isn't
actually there:

- **EventBridge** (the intended session event bus for the call stream)
  is not deployed. The demo instead uses a direct synchronous request
  per submitted trajectory (Lambda) or a direct WebSocket connection to
  the FastAPI process (local/demo build). Wiring EventBridge would mean
  each tool call publishing an event that a Lambda consumer picks up and
  evaluates incrementally, persisting graph state to `SessionGraphTable`
  between calls.

- **PolicyTable** is provisioned (schema and IAM wiring are real) but
  `infra/lambda_handler.py` currently reads policy from the bundled
  `policy/*.yaml` files packaged with the Lambda, not from this table at
  request time. Reading from DynamoDB at cold start is a small, well-
  scoped change (fetch conflict-class/clearance items, reshape into the
  same `engine.policy.Policy` object `load_policy` already builds) but
  wasn't done here for time; it's the natural next step for making
  policy edits deployable without a redeploy.

- **SessionGraphTable** is provisioned but unused by
  `EvaluateSessionFunction`, which evaluates one complete submitted
  trajectory per request (mirroring `POST /api/sessions/{id}/evaluate`
  in the local API) rather than incrementally across separate
  invocations. Persisting per-call graph state to this table is what an
  EventBridge-driven, one-call-per-invocation architecture would need.

None of this affects the decision engine itself: `engine/` is identical
between the local FastAPI build and this Lambda adapter (same import,
same function call). What's incomplete is purely the event-streaming
and policy-hot-reload plumbing around it.
