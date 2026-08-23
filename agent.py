# Import necessary tools (libraries) for our program to work
import json       
import logging    
import os         
import requests   
import sys        
from openai import OpenAI  

# Setup logging for our "Visible Execution Trace"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("CaseworkerAgent")

class CaseworkerAgent:
    
    # We added an "amendment_path" to our setup so we can pass the new rules
    def __init__(self, queue_path, policy_path, amendment_path="Amendment ACA-2026-2.md", api_base_url="http://127.0.0.1:8083"):
        self.queue_path = queue_path
        self.policy_path = policy_path
        self.amendment_path = amendment_path
        self.api_base_url = api_base_url
        
        # Load the original policy
        self.policy_text = self._load_file(self.policy_path)
        
        # Load Day 2 amendment if present (handles 'Amendment ACA-2026-2.md' or 'amendment-ACA-2026-2.md')
        if self.amendment_path and os.path.exists(self.amendment_path):
            self.amendment_text = self._load_file(self.amendment_path)
            self.full_rulebook = f"{self.policy_text}\n\nAMENDMENTS:\n{self.amendment_text}"
        elif os.path.exists("amendment-ACA-2026-2.md"):
            self.amendment_text = self._load_file("amendment-ACA-2026-2.md")
            self.full_rulebook = f"{self.policy_text}\n\nAMENDMENTS:\n{self.amendment_text}"
        elif os.path.exists("Amendment ACA-2026-2.md"):
            self.amendment_text = self._load_file("Amendment ACA-2026-2.md")
            self.full_rulebook = f"{self.policy_text}\n\nAMENDMENTS:\n{self.amendment_text}"
        else:
            self.full_rulebook = self.policy_text
        
        queue_text = self._load_file(self.queue_path)
        self.queue_data = json.loads(queue_text)
        
        api_key = os.getenv("GEMINI_API_KEY")
        base_url = os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
        self.model = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")
        
        if api_key == "":
            logger.warning("No API key found. Continuing with 'missing_key'.")
            final_api_key = "missing_key"
        else:
            final_api_key = api_key

        self.llm = OpenAI(base_url=base_url, api_key=final_api_key)
        
    def _load_file(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def fetch_history(self, resident_ref):
        # We always fetch history first. This ensures if the case is handed off later,
        # we have already saved the human caseworker from doing this step!
        try:
            full_url = f"{self.api_base_url}/residents/{resident_ref}"
            response = requests.get(full_url, timeout=5)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": "History not found"}
                
        except Exception as e:
            logger.error(f"Failed to fetch history for {resident_ref}: {e}")
            return {"error": "Connection failed"}

    def evaluate_policy_and_draft(self, referral, history):
        # DAY 2 UPDATE: We updated the prompt to handle three different statuses:
        # 'authorized', 'escalate', or 'hand_off'. 
        prompt = f"""
        You are a policy compliance engine. Evaluate the referral against the rulebook (Policy + Amendments).
        
        1. If it violates standard authority (e.g., out of bounds), set status to 'escalate'.
        2. If it triggers a caseworker hand-off (e.g., household includes someone under 18 based on the history), set status to 'hand_off'. YOU MUST NOT DRAFT A NOTE.
        3. If it is permitted, set status to 'authorized' and draft a brief triage note.
        
        RULEBOOK:
        {self.full_rulebook}
        
        REFERRAL:
        {json.dumps(referral)}
        
        RESIDENT HISTORY:
        {json.dumps(history)}
        """
        
        response = self.llm.chat.completions.create(
            model=self.model,
            response_format={ "type": "json_object" }, 
            # Notice we changed 'authorized': bool to 'status': str to handle the 3 new possibilities
            messages=[
                {"role": "system", "content": "You output strict JSON: {'status': 'authorized'|'escalate'|'hand_off', 'violated_section': str|null, 'reason': str, 'draft_note': str|null}"},
                {"role": "user", "content": prompt}
            ]
        )
        
        return json.loads(response.choices[0].message.content)

    def process_queue(self):
        logger.info(f"Loaded {len(self.queue_data)} referrals from overnight queue.")
        
        # DAY 2 UPDATE: We now have TWO separate lists for cases we cannot process.
        escalations = []
        handoffs = []

        for referral in self.queue_data:
            ref_id = referral.get("referral_id", "UNKNOWN")
            resident_ref = referral.get("resident_ref")
            
            logger.info("-" * 50)
            logger.info(f"Processing Referral: {ref_id} | Resident: {resident_ref}")
            
            try:
                # Step 1: Pull History (We do this no matter what, preserving work in progress)
                history = self.fetch_history(resident_ref)
                
                # Step 2: Check Policy
                eval_result = self.evaluate_policy_and_draft(referral, history)
                status = eval_result.get("status")
                
                # Step 3A: Handle Escalations (The Department must decide)
                if status == "escalate":
                    logger.warning(f"ESCALATION TRIGGERED: Violated {eval_result.get('violated_section')}.")
                    escalations.append({
                        "referral": referral,
                        "history_summary": history,
                        "reason": eval_result.get('reason')
                    })
                    continue 
                
                # Step 3B: Handle Hand-offs (Caseworker must do this, e.g., child in home)
                elif status == "hand_off":
                    logger.warning(f"HAND-OFF REQUIRED: {eval_result.get('reason')}")
                    logger.info("Preserving fetched history and handing off to human caseworker.")
                    handoffs.append({
                        "referral": referral,
                        "history_summary": history, # We pass the work we already did to the human!
                        "reason": eval_result.get('reason')
                    })
                    continue
                
                # Step 4: If Authorized, hit the hard gate
                elif status == "authorized":
                    draft = eval_result.get("draft_note")
                    logger.info("Agent evaluated policy as SAFE and drafted triage note.")
                    self.commit_irreversible_action(ref_id, draft)

            except Exception as e:
                logger.error(f"Critical failure processing {ref_id}: {str(e)}")

        # Save escalations for review
        if len(escalations) > 0:
            with open("escalations_queue.json", "w", encoding="utf-8") as f:
                json.dump(escalations, f, indent=2) 
            logger.info(f"Wrote {len(escalations)} escalated cases to escalations_queue.json.")

        # Save hand-offs for human caseworkers
        if len(handoffs) > 0:
            with open("handoffs_queue.json", "w", encoding="utf-8") as f:
                json.dump(handoffs, f, indent=2) 
            logger.info(f"Wrote {len(handoffs)} hand-off cases to handoffs_queue.json.")

        logger.info("Morning queue processing complete.")

    def commit_irreversible_action(self, ref_id, draft):
        # THE HARD GATE: Completely isolated from the AI.
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
        policy_path="authority-policy.md",
        amendment_path="Amendment ACA-2026-2.md" 
    )
    agent.process_queue()
