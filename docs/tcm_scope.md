# TCM-RAG Scope and Abstention Policy

This file defines the limited research scope for the standalone TCM-RAG module. It is a routing and abstention policy, not a diagnosis system.

## Supported

The current corpus supports only educational TCM pattern-direction discussion for:

- sleep problems
- fatigue and low energy
- appetite, bloating, and digestion
- emotional stress and constraint symptoms
- headache and dizziness
- mild throat irritation and cough presentations
- cold/heat signs and sweating
- lower-back soreness, tinnitus, and deficiency-related presentations

Supported means the system may retrieve local evidence and, only if evidence passes the threshold, generate a cautious TCM perspective grounded in retrieved entries.

## Insufficient information

Examples:

- “I feel unwell.”
- “我最近不舒服。”
- “몸이 좀 이상해요.”

Behavior:

- abstain
- ask a small number of clarifying questions
- do not infer a pattern
- do not show formulas or herbs

## Out of scope

Examples:

- acute trauma and wounds
- fractures and structural injury
- severe bleeding or suspected acute infection that needs clinical assessment
- cancer or serious-disease treatment advice
- medication dosing
- diagnosis or prescription requests

Behavior:

- abstain
- do not retrieve irrelevant TCM evidence
- do not show formulas, herbs, or treatment instructions
- recommend professional assessment or future routing to an appropriate module

## Safety critical

Examples:

- severe chest pain
- breathing difficulty
- fainting or confusion
- stiff neck with fever
- uncontrolled bleeding
- severe allergic reaction
- suicidal or self-harm content

Behavior:

- do not generate TCM syndrome differentiation
- do not show formulas or herbs
- provide concise safety-first educational guidance
- mark `generation_source = "safety_rule"` and `abstained = true`

## Evidence insufficient

If scope is potentially relevant but retrieval finds no evidence above `MIN_RELEVANCE_SCORE`, generation is blocked. The evidence list, patterns, and formula examples remain empty.
