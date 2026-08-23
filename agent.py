import json
import logging
import os
import requests
import sys
from openai import OpenAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("CaseworkerAgent")

class CaseworkerAgent:
    def __init__(self, queue_path, policy_path, api_base_url="http://127.0.0.1:8083", model=None):
        self.queue_path = queue_path
        self.policy_path = policy_path
        self.api_base_url = api_base_url
        self.policy_text = self._load_file(self.policy_path)
        self.queue_data = json.loads(self._load_file(self.queue_path))
        
        gemini_key = os.getenv("GEMINI_API_KEY") 

        if gemini_key:
            api_key = gemini_key
            default_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            default_model = "gemini-3.5-flash"
        else:
            api_key = ""
            default_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            default_model = "gemini-3.6-flash"
            logger.warning("No API key found in GEMINI_API_KEY, GROQ_API_KEY, or OPENAI_API_KEY environment variables.")

        base_url = os.getenv("LLM_BASE_URL", default_base_url)
        self.model = os.getenv("LLM_MODEL", model or default_model)
        
        if base_url:
            self.llm = OpenAI(base_url=base_url, api_key=api_key or "missing_key")
        else:
            self.llm = OpenAI(api_key=api_key or "missing_key")
        
    def _load_file(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def fetch_history(self, resident_ref):
        """Fetches full resident history from the mock API."""
        try:
            response = requests.get(f"{self.api_base_url}/residents/{resident_ref}", timeout=5)
            if response.status_code == 200:
                return response.json()
            return {"error": "History not found or API error"}
        except Exception as e:
            logger.error(f"Failed to fetch history for {resident_ref}: {e}")
            return {"error": "Connection failed"}

    def evaluate_policy_and_draft(self, referral, history):
        """
        Uses LLM to evaluate the request against the dynamic policy.
        Returns JSON containing authorization status, violated section (if any), and a draft note.
        """
        prompt = f"""
        You are a policy compliance engine. Evaluate the referral against the authority policy.
        If the 'requested_action' violates Section 3 of the policy, you MUST reject it and provide the section violated.
        If it is permitted (e.g., merely drafting a note or categorizing), set authorized to true and draft a brief triage note.
        
        POLICY:
        {self.policy_text}
        
        REFERRAL:
        {json.dumps(referral)}
        
        RESIDENT HISTORY:
        {json.dumps(history)}
        """
        
        response = self.llm.chat.completions.create(
            model=self.model,
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": "You output strict JSON: {'authorized': bool, 'violated_section': str|null, 'reason': str, 'draft_note': str|null}"},
                {"role": "user", "content": prompt}
            ]
        )
        return json.loads(response.choices[0].message.content)

    def process_queue(self):
        logger.info(f"Loaded {len(self.queue_data)} referrals from overnight queue.")
        escalations = []

        for referral in self.queue_data:
            ref_id = referral.get("referral_id", "UNKNOWN")
            resident_ref = referral.get("resident_ref")
            logger.info("-" * 50)
            logger.info(f"Processing Referral: {ref_id} | Resident: {resident_ref}")
            
            try:
                # 1. Pull Resident History
                history = self.fetch_history(resident_ref)
                
                # 2. Dynamic Policy Evaluation
                eval_result = self.evaluate_policy_and_draft(referral, history)
                
                # 3. Handle Escalation
                if not eval_result.get("authorized"):
                    logger.warning(f"GUARDRAIL TRIGGERED: Out of authority limit. Reason: {eval_result.get('reason')}")
                    logger.warning(f"Violated Section: {eval_result.get('violated_section')}")
                    escalations.append({
                        "referral": referral,
                        "history_summary": history,
                        "violation": eval_result.get('violated_section'),
                        "reason": eval_result.get('reason')
                    })
                    continue 
                
                # 4. Draft Note & Hit Hard Approval Gate
                draft = eval_result.get("draft_note")
                logger.info("Agent drafted triage note successfully.")
                self.commit_irreversible_action(ref_id, draft)

            except Exception as e:
                # Handle partial failure mid-run safely
                logger.error(f"Critical failure processing {ref_id}: {str(e)}")
                logger.info("Recovering and continuing to next referral...")

        # Output Escaped Queue
        if escalations:
            with open("escalations_queue.json", "w", encoding="utf-8") as f:
                json.dump(escalations, f, indent=2)
            logger.info(f"Wrote {len(escalations)} escalated cases to escalations_queue.json for supervisor review.")

        logger.info("Morning queue processing complete.")

    def commit_irreversible_action(self, ref_id, draft):
        """
        THE HARD GATE: Structurally isolated from AI tools. 
        Irreversible actions demand explicit human permission.
        """
        print(f"\n[SYSTEM HALT] Irreversible action pending for {ref_id}.")
        print(f"Draft Triage Note: {draft}")
        approval = input("Approve recording this triaged note to the live system? (y/n): ")
        if approval.lower() != 'y':
            logger.warning(f"Human rejected action for {ref_id}. Skipping.")
            return

        logger.info(f"SUCCESS: Triage completed and saved for {ref_id}.")

if __name__ == "__main__":
    agent = CaseworkerAgent(
        queue_path="referral-queue.json",
        policy_path="authority-policy.md"
    )
    agent.process_queue()
