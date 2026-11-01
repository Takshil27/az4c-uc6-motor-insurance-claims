# Motor insurance claims - Associate submission

## Set up and run

Requires Python 3.12. No third-party packages are required.

```powershell
cd code
Copy-Item .env.example .env
# Add a Gemini API key to .env for advisory model reviews.
$env:DATA_DIR = "C:\path\to\AZ4C-UC6-motor-insurance-claims"
python -m app run --case ..\samples\UC6-S01.json --out out\UC6-S01.json
python -m app eval --cases tests\cases
python -m app serve
```

`DATA_DIR` must point to the root of the supplied data pack. The application reads the SQLite database and Markdown packet directly from that folder; it never changes them. Results, decision letters and execution traces are written under `code/mock_system/`.

## Design

The orchestrator makes a real branching plan and stops as soon as a specialist gives a decisive result:

1. `packet-completeness` checks the files actually present in the claim folder.
2. `coverage` checks period, plan and exclusions.
3. `evidence-consistency` compares the accident date and driver in the claimant and surveyor evidence.
4. `fraud-screen` checks the three Claims Manual warning signs.
5. `settlement` applies surveyor values, depreciation, deductibles and the IDV cap.

Each specialist receives claim data only through the read-only `ClaimsTools` interface. Each response is schema-checked and retried once when its tools fail or its structured result is invalid. See [the architecture diagram](docs/architecture.md).

## Tools

`ClaimsTools` exposes parameterised SQLite queries for claims, policies, garages, paid prior claims and the part rate card, plus a constrained local Markdown reader for policy/manual and claim packets. It rejects missing records, database errors and paths outside `DATA_DIR/docs`. Evidence inside a Markdown file is data, not an instruction.

## Models used and why

When `GEMINI_API_KEY` is configured, each specialist requests a brief advisory quality review from Gemini `gemini-3.1-flash-lite`. Every attempted model call (including skipped and failed calls) is written to `mock_system/traces/<trace_id>.json`.

The model is deliberately non-authoritative. A deterministic calculation engine enforces PW/CM rules, validates all agent findings and produces the result even if a key is absent, a provider rate-limits or a reply is malformed. This preserves reproducible monetary outcomes and prevents prompt injection in claim documents from changing behaviour.

## Failure handling

- Missing claim records, documents or database failures produce a clear command failure after one retry; no fabricated decision is saved.
- Missing packet files produce `request_documents` immediately as required by CM 2.4.
- Invalid specialist results and transient tool failures are retried once and recorded in the trace.
- Provider failures are logged and use the deterministic fallback, so decisions do not depend on network availability.
- Rejections, referrals and settlements over ₹50,000 set `needs_human: true` for the Part B approval workflow.

## Tests and score

Ten local cases cover full and partial payments, theft, three missing-packet variations, an inactive policy, liability-only cover, fraud referral and a high-value settlement. Run `python -m app eval --cases tests/cases`; it writes `tests/score.json`. The supplied five sample cases score 100% with the same command.

## Bonus: approval screen

Run `python -m app serve` and open `http://127.0.0.1:8080`. The local screen lists the latest human-review cases (rejections, referrals and payouts over ₹50,000), displays the recommended decision and policy evidence, and records Approve, Request change or Reject actions in `mock_system/approvals.jsonl`. It is dependency-free and intentionally preserves the Part A behaviour of writing its decision immediately.
