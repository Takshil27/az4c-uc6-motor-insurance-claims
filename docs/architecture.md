# UC6 architecture

```mermaid
flowchart TD
    C[Case JSON: claim_id] --> O[Orchestrator]
    O --> P[Packet completeness agent]
    P -->|missing| RD[request_documents]
    P -->|complete| CV[Coverage agent]
    CV -->|not covered| RJ[reject]
    CV -->|covered| EV[Evidence consistency agent]
    EV -->|conflict| RF[refer]
    EV -->|consistent| FS[Fraud screen agent]
    FS -->|warning sign| RF
    FS -->|clear| ST[Settlement agent]
    ST --> PD[pay_full or pay_partial]
    RD --> W[Mock claims system + letter + trace]
    RJ --> W
    RF --> W
    PD --> W

    T[(ClaimsTools)] --- P
    T --- CV
    T --- FS
    T --- ST
    D[(SQLite + Markdown in DATA_DIR)] --- T
    M[Gemini advisory review] -. logged, never authoritative .-> P
    M -.-> CV
    M -.-> EV
    M -.-> FS
    M -.-> ST
```

The solid path is the decision path. The dashed model-review path can fail without changing the deterministic, policy-grounded result. Each specialist result is validated and retried once before the orchestrator acts on it.
