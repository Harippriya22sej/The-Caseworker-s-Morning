# AI Usage Declaration

In accordance with the hackathon rules, here is how AI was utilized in this submission:

*   **Scaffolding and Boilerplate:** AI was used to quickly generate the Python boilerplate for reading the JSON/Markdown files, making HTTP requests to the Resident History API, and setting up the basic logging structure.
*   **Prompt Engineering:** AI assisted in drafting the system prompt that forces the LLM to return strict JSON mapping the `requested_action` to Section 3 of the policy.
*   **Guardrail Design:** The architectural decision to use a hard Python `input()` gate (Structural Capability Isolation) was manually designed to strictly satisfy the problem's "hard approval gate" requirement, but AI was used to write the surrounding code for it. 
*   **Code Review:** AI was used to format the final code and ensure the `try-except` blocks properly isolated individual referrals so one failure wouldn't derail the whole run.

I own every line of code in this repository and can fully explain the structural isolation that prevents the agent from taking unauthorized actions.
