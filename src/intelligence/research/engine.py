import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from .schemas import (
    AggregatedIntelligence,
    ResearchThesis,
    ObservedFacts,
    TokenAssessment,
    ValidationCriteria,
    ChangeDetectionResult
)

logger = logging.getLogger(__name__)

class AIResearchEngine:
    """
    Synthesizes multiple intelligence streams into a coherent token thesis,
    and detects material changes over time.
    """
    
    def __init__(self):
        # In-memory storage for previous theses as requested.
        # token_address -> list of ResearchThesis (ordered by timestamp)
        self._theses_store: Dict[str, List[ResearchThesis]] = {}
        
    def generate_thesis(self, intelligence: AggregatedIntelligence) -> ResearchThesis:
        """
        Generates a comprehensive research thesis for a given token opportunity.
        """
        logger.info(f"Generating AI research thesis for {intelligence.token_address} on {intelligence.chain}")
        
        # 1. Construct the prompt
        prompt = self._build_thesis_prompt(intelligence)
        
        # 2. Call the LLM (Mocked for now)
        raw_response = self._call_llm(prompt, response_format="json")
        
        # 3. Parse and construct the Pydantic model
        try:
            parsed_data = json.loads(raw_response)
            
            # Map LLM JSON output to our internal schemas
            observed_facts = ObservedFacts(**parsed_data.get("observed_facts", {}))
            assessment = TokenAssessment(**parsed_data.get("assessment", {}))
            validation = ValidationCriteria(**parsed_data.get("validation", {}))
            
            thesis = ResearchThesis(
                token_address=intelligence.token_address,
                observed_facts=observed_facts,
                assessment=assessment,
                validation=validation,
                overall_conviction=parsed_data.get("overall_conviction", 0.5),
                recommended_action=parsed_data.get("recommended_action", "HOLD"),
                raw_prompt=prompt,
                raw_response=raw_response
            )
            
            # Store it in memory
            self._store_thesis(thesis)
            
            return thesis
        except Exception as e:
            logger.error(f"Failed to parse LLM thesis generation response: {e}")
            raise

    def detect_thesis_change(self, current_intelligence: AggregatedIntelligence) -> Optional[ChangeDetectionResult]:
        """
        Compares new intelligence against the most recent thesis to detect material changes
        (e.g., LP pull, developer sale) without rewriting a redundant thesis.
        """
        previous_thesis = self._get_latest_thesis(current_intelligence.token_address)
        if not previous_thesis:
            logger.info("No previous thesis found. Cannot detect change.")
            return None
            
        logger.info(f"Detecting changes for {current_intelligence.token_address} against thesis {previous_thesis.thesis_id}")
        
        # 1. Construct the prompt for change detection
        prompt = self._build_change_detection_prompt(current_intelligence, previous_thesis)
        
        # 2. Call the LLM
        raw_response = self._call_llm(prompt, response_format="json")
        
        # 3. Parse the result
        try:
            parsed_data = json.loads(raw_response)
            
            result = ChangeDetectionResult(
                token_address=current_intelligence.token_address,
                previous_thesis_id=previous_thesis.thesis_id,
                is_material_change=parsed_data.get("is_material_change", False),
                change_description=parsed_data.get("change_description", "No material change detected."),
                affected_areas=parsed_data.get("affected_areas", []),
                requires_new_thesis=parsed_data.get("requires_new_thesis", False)
            )
            return result
        except Exception as e:
            logger.error(f"Failed to parse change detection response: {e}")
            raise

    # --- Internal Methods ---

    def _store_thesis(self, thesis: ResearchThesis):
        """Stores the thesis in-memory."""
        if thesis.token_address not in self._theses_store:
            self._theses_store[thesis.token_address] = []
        self._theses_store[thesis.token_address].append(thesis)

    def _get_latest_thesis(self, token_address: str) -> Optional[ResearchThesis]:
        """Retrieves the most recent thesis for a token."""
        theses = self._theses_store.get(token_address, [])
        if not theses:
            return None
        # Assuming they are appended in chronological order
        return theses[-1]

    def _build_thesis_prompt(self, intelligence: AggregatedIntelligence) -> str:
        """Constructs the prompt for the LLM based on aggregated intelligence."""
        # Convert the Pydantic model to a JSON string for the prompt
        data_json = intelligence.model_dump_json(indent=2)
        
        prompt = f"""
You are an elite crypto AI research analyst. Your job is to consume the following structured intelligence data for a token and produce a coherent token assessment.

RULES:
1. Clearly separate observed facts (data) from your interpretations (assessment).
2. Generate a bull case, bear case, risk summary, opportunity summary, historical comparison, similar-token analysis, and thesis durability.
3. Explicitly state what future signals would validate or invalidate this thesis.
4. Output your response as a strictly formatted JSON object.

RAW INTELLIGENCE DATA:
{data_json}

EXPECTED JSON SCHEMA:
{{
  "observed_facts": {{
    "liquidity_state": "...",
    "ownership_state": "...",
    "social_state": "...",
    "security_state": "...",
    "smart_money_state": "..."
  }},
  "assessment": {{
    "bull_case": "...",
    "bear_case": "...",
    "risk_summary": "...",
    "opportunity_summary": "...",
    "historical_comparison": "...",
    "similar_token_analysis": "...",
    "thesis_durability": "..."
  }},
  "validation": {{
    "supporting_signals": ["...", "..."],
    "invalidating_signals": ["...", "..."]
  }},
  "overall_conviction": 0.0 to 1.0,
  "recommended_action": "STRONG BUY | BUY | HOLD | AVOID | SELL"
}}
"""
        return prompt

    def _build_change_detection_prompt(self, current: AggregatedIntelligence, previous: ResearchThesis) -> str:
        """Constructs the prompt to detect material changes."""
        
        current_data = current.model_dump_json(indent=2)
        previous_thesis = previous.model_dump_json(indent=2, include={"observed_facts", "assessment", "validation"})
        
        prompt = f"""
You are a crypto thesis-invalidation engine. Your job is to compare the LATEST intelligence with the PREVIOUS thesis, and determine if any MATERIAL changes have occurred that break or significantly alter the thesis (e.g., major LP removal, dev selling, social collapse, market regime shift).

RULES:
1. Ignore minor fluctuations (e.g., 5% price drop, normal trading volume).
2. Look for hard evidence that contradicts the previous `invalidating_signals` or drastically changes the `observed_facts`.
3. Output your response as a strictly formatted JSON object.

PREVIOUS THESIS:
{previous_thesis}

LATEST INTELLIGENCE:
{current_data}

EXPECTED JSON SCHEMA:
{{
  "is_material_change": true/false,
  "change_description": "Detailed explanation of what changed and why it matters...",
  "affected_areas": ["liquidity", "security", "social"],
  "requires_new_thesis": true/false
}}
"""
        return prompt

    def _call_llm(self, prompt: str, response_format: str) -> str:
        """
        MOCK METHOD: Simulates an LLM call. 
        In production, replace this with OpenAI, Anthropic, or local model SDK calls.
        """
        logger.info("Calling MOCK LLM...")
        
        # Very basic heuristic to return a mock response based on the prompt type
        if "EXPECTED JSON SCHEMA:\n{\n  \"observed_facts\":" in prompt:
            # Thesis Generation Mock
            mock_response = {
                "observed_facts": {
                    "liquidity_state": "Liquidity is $500k, locked for 6 months.",
                    "ownership_state": "Top 10 holders own 15% of supply. Dev wallet holds 2%.",
                    "social_state": "Twitter followers grew by 20% in 24h. Positive sentiment.",
                    "security_state": "Contract is verified, no mint function, ownership renounced.",
                    "smart_money_state": "Net inflow of $50k from 3 known smart money addresses."
                },
                "assessment": {
                    "bull_case": "Strong community growth coupled with smart money accumulation suggests an impending breakout if market regime remains positive.",
                    "bear_case": "If narrative dies down, lack of immediate utility could lead to a slow bleed.",
                    "risk_summary": "Low security risk. Medium financial risk due to beta to broader market. Low narrative risk.",
                    "opportunity_summary": "High-conviction early momentum play with solid fundamentals.",
                    "historical_comparison": "Similar accumulation pattern to TokenX before its 10x run last cycle.",
                    "similar_token_analysis": "Outperforming TokenY in social metrics but lagging in liquidity.",
                    "thesis_durability": "Short to medium term (1-4 weeks)."
                },
                "validation": {
                    "supporting_signals": ["Continued smart money inflows", "CEX listing announcements", "Holding support at $0.05"],
                    "invalidating_signals": ["Dev wallet movement", "Liquidity unlock/removal", "Top 10 holders selling > 20% of their bags"]
                },
                "overall_conviction": 0.85,
                "recommended_action": "STRONG BUY"
            }
            return json.dumps(mock_response)
            
        elif "EXPECTED JSON SCHEMA:\n{\n  \"is_material_change\":" in prompt:
            # Change Detection Mock
            mock_response = {
                "is_material_change": True,
                "change_description": "Mocked change: Detected a significant decrease in liquidity and dev wallet movement, hitting the invalidation criteria.",
                "affected_areas": ["liquidity", "ownership"],
                "requires_new_thesis": True
            }
            return json.dumps(mock_response)
            
        else:
            return "{}"
