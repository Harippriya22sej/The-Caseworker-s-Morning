# Architectural Decisions

## The Structural Guardrail (What the agent cannot do)
As required by the problem brief, this agent is **structurally incapable of committing an irreversible action without a human**. 

**How I know it cannot bypass this:**
The language model is entirely sandboxed from execution. It is only permitted to read the referral, read the history API, and return a structured JSON response containing its policy evaluation and a drafted triage note. The LLM is not provided with any function-calling tools or API keys that can write to a database. 

The actual "commit" action is handled strictly by the Python execution loop (`commit_irreversible_action()`), which intercepts the LLM's draft and physically halts the thread using a terminal `input()` prompt. Without a human pressing 'y' on the keyboard, the state cannot change. A guardrail based only on a system prompt is not a guardrail, so this solution relies on execution environment isolation.

## Policy as the Source of Truth & Day 2 Amendment Handling
I chose to treat `authority-policy.md` and any subsequent amendments (like `Amendment ACA-2026-2.md`) as dynamic data rather than hardcoding business rules into the Python code. 

When Day 2 introduced `Amendment ACA-2026-2.md` (safeguarding restriction 3.9 for households with children under 18), the agent dynamically loaded and appended the amendment into the LLM's rulebook (`self.full_rulebook`). Without refactoring the architectural boundary:
* **Section 3.9 Safeguarding**: The agent detects child-in-household cases, complies with Section 2.2 by refusing to draft a triage note, and preserves the fetched history.
* **Distinct Hand-off Queue (`handoffs_queue.json`)**: Satisfies Section 3.3 by writing ordinary caseworker hand-offs to `handoffs_queue.json`, keeping them distinct from supervisor escalations (`escalations_queue.json`).

## Escalation Handling
Escalations are not just skipped; they are packaged with the full referral context, the resident's history, and the specific section of the policy that was violated. This satisfies the requirement to give the supervisor enough context to act without re-reading the case.

## What was cut for time / Not done
*   **User Interface:** I relied entirely on a CLI and a readable standard output trace, as the brief explicitly stated UI was not assessed.
*   **Complex Retry Logic:** If the mock API times out, the agent logs an error and skips to the next referral rather than implementing exponential backoff. 

## What I would fix first
Currently, escalated referrals are written to `escalations_queue.json` and hand-offs to `handoffs_queue.json`. In a production environment, I would wire these functions directly into dedicated message queues (like RabbitMQ or AWS SQS) to immediately notify the supervisor and caseworker dashboards.
