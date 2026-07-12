# TCM-RAG Architecture

The TCM-RAG module is a standalone research prototype inside the larger MediRAG-Judge architecture. It does not implement MediRAG-West, multi-agent debate, SafeJudge, or an integrated dual-medicine answer.

Pipeline:

1. Request validation
2. Safety-critical screening
3. Scope classification
4. Evidence retrieval
5. Evidence gate
6. Grounded generation or local fallback
7. Deterministic confidence calculation
8. Structured API response for future Debate/Judge stages

```mermaid
flowchart TD
  Q["User health question"] --> S["Safety screening"]
  S -->|safety_critical| SR["Safety-rule abstention"]
  S --> C["Scope classification"]
  C -->|out_of_scope| OR["Scope-rule abstention"]
  C -->|insufficient_information| IR["Clarifying-question abstention"]
  C --> R["Retrieval"]
  R --> G["Evidence gate"]
  G -->|no meaningful evidence| ER["Evidence-insufficient abstention"]
  G -->|evidence passes| L["SiliconFlow/OpenAI-compatible LLM"]
  L --> A["Structured TCM response"]
  G --> F["Local fallback if provider unavailable"]
```

The LLM receives only the user question, optional non-identifying context, retrieved evidence, source metadata, safety constraints, and an output schema. It is not allowed to invent citations, prescriptions, herbs, doses, or treatment claims.
