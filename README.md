# The-Caseworker-s-Morning
Build an agent that performs a caseworker’s routine morning sequence end to end, and stops to ask a human before doing anything that cannot be undone.
Here is a clean, beginner-friendly `README.md` file designed to meet the exact requirements of your submission.

# The Caseworker's Morning Agent

This repository contains a solution for **Brite Spark 2026: Problem 5**. It implements an AI agent that automates routine casework triage while strictly adhering to a dynamic authority policy. The agent stops at a hard gate before taking irreversible actions and safely routes unauthorized cases.

## Features

* **Policy as Data:** The agent reads rules directly from markdown files, adapting to day-two amendments automatically without code changes.


* **Hard Approval Gate:** Irreversible actions require explicit, structural human approval via command-line input.


* **Mid-Run Resilience:** If a single referral fails, the agent recovers and safely processes the remainder of the queue.


* **Context-Rich Escalations:** Out-of-bounds requests are categorized properly with the full resident history attached to save human effort.



---

## Setup Instructions

Follow these steps to run the agent from a clean clone.

1. Clone this repository to your local machine.
2. Ensure you have Python installed.
3. Install the required external libraries using `pip install openai requests`.
4. Set your API key as an environment variable by running `export GEMINI_API_KEY="your_api_key_here"`.
5. Ensure the mock resident-history API is running locally.

---

## Running the Agent

Execute the main Python script from your terminal:

> `python caseworker_agent.py`

The agent will output a **visible execution trace** directly to the console. If it evaluates a referral as safe, the system will halt and prompt you for a `y/n` input to approve saving the triage note.
