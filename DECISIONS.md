# Architectural Decisions

## The Structural Guardrail (What the agent cannot do)
As required by the problem brief, this agent is **structurally incapable of committing an irreversible action without a human**. 

**How I know it cannot bypass this:**
The language model is entirely sandboxed from execution. It is only permitted to read the referral, read the history API, and return a structured JSON response containing its policy evaluation and a drafted triage note. The LLM is not provided with any function-calling tools or API keys that can write to a database. 

The actual "commit" action is handled strictly by the Python execution loop (`commit_irreversible_action()`), which intercepts the LLM's draft and physically halts the thread using a terminal `input()` prompt. Without a human pressing 'y' on the keyboard, the state cannot change. A guardrail based only on a system prompt is not a guardrail, so this solution relies on execution environment isolation.

## Policy as the Source of Truth
I chose to treat `authority-policy.md` as dynamic data rather than hardcoding its rules into the Python logic. The text of the policy is injected directly into the LLM's context window. If the policy changes on Day 2, the markdown file can simply be updated, and the agent's boundaries will automatically shift without requiring a single change to the Python code. 

## Escalation Handling
Escalations are not just skipped; they are packaged with the full referral context, the resident's history, and the specific section of the policy that was violated. This satisfies the requirement to give the supervisor enough context to act without re-reading the case.

## What was cut for time / Not done
*   **User Interface:** I relied entirely on a CLI and a readable standard output trace, as the brief explicitly stated UI was not assessed.
*   **Complex Retry Logic:** If the mock API times out, the agent logs an error and skips to the next referral rather than implementing exponential backoff. 

## What I would fix first
Currently, escalated referrals are written to a local `escalations_queue.json` file. In a production environment, I would wire the `escalate` function directly into a proper messaging queue (like RabbitMQ or AWS SQS) to immediately notify the supervisor's dashboard.
