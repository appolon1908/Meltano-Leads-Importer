# Meltano-Leads-Importer — Architecture Charts

> Repository: `appolon1908/Meltano-Leads-Importer`  
> Baseline branch: `main`  
> Repository-local visual architecture. Keep these diagrams aligned with code, contracts, data ownership and deployment.

## 1. System context
```mermaid
flowchart LR
 A["Lead source files/services"] --> B["Meltano pipelines"]
 B --> R["Meltano-Leads-Importer<br/>Lead ingestion authority"]
 R --> S["raw import batches / provenance"]
 R --> D["Leads API / staging DB"]
```

## 2. Internal component architecture
```mermaid
flowchart TB
 I["Entrypoint / UI / API / CLI"] --> P["Identity, policy, validation"]
 P --> C["Core domain / orchestration"]
 C --> S["State / configuration / persistence"]
 C --> A["Adapters / integrations"]
 A --> X["Approved dependencies"]
 C --> O["Metrics, logs, traces, audit"]
```

## 3. Critical flow
```mermaid
sequenceDiagram
 participant U as Caller
 participant B as Meltano-Leads-Importer
 participant P as Policy
 participant C as Core
 participant S as State
 participant X as Dependency
 U->>B: Request / event / action
 B->>P: Authenticate + validate
 P-->>B: Decision
 B->>C: Extract source, load raw staging, validate batch and hand off
 C->>S: Read / persist
 C->>X: Bounded integration
 X-->>C: Result / readback
 C-->>U: Normalized response
```

## 4. Deployment and promotion
```mermaid
flowchart LR
 F["Feature branch"] --> T["Tests / validation"]
 T --> PR["Pull request + review"]
 PR --> CI["CI green"]
 CI --> ST["Staging / isolated verification"]
 ST --> EX["Exact-SHA certification"]
 EX --> G{"Production approval?"}
 G -- No --> ST
 G -- Yes --> P["Production promotion"]
 P --> H["Health/readiness + rollback check"]
```

## 5. Observability and recovery
```mermaid
flowchart LR
 R["Meltano-Leads-Importer"] --> M["Metrics"]
 R --> L["Logs / audit"]
 R --> T["Traces / correlation"]
 M --> O["Observability stack"]
 L --> O
 T --> O
 O --> A["Dashboards / alerts"]
 R --> B["Backup / config snapshot"]
 B --> RR["Restore / rollback rehearsal"]
```

## Ownership notes
- **Role:** Lead ingestion authority
- **Primary boundary:** Meltano pipelines
- **State/config:** raw import batches / provenance
- **Dependencies/consumers:** Leads API / staging DB
- Cross-repository effects must use reviewed contracts; production effects remain separately gated.
