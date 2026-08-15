# Multi-agent architecture

Agents are registry-driven and share `ResearchAgentOutput`.

| Agent | Scope | Hard boundary |
|---|---|---|
| Query Planner | language, intent, routing, filters, safety | classification summaries only |
| Syndrome Differentiation | pattern concepts and symptom relationships | no diagnosis |
| Herbal Knowledge | traditional categories and educational content | no dosing or prescribing |
| Acupuncture and Meridian | conceptual relationships | no procedural needling instruction |
| Constitution | constitution theory | uncertainty required |
| Dietary Therapy | traditional food-property concepts | separated from modern nutrition evidence |
| Lifestyle/Yangsheng | sleep, routine, movement, seasonal concepts | conservative education only |

Conditions present agents independently, aggregate with deterministic evidence/confidence weights, run critique/revision, or pass outputs to judges. Debate traces contain only visible critiques, evidence references, revisions, agreements, and unresolved conflicts.
