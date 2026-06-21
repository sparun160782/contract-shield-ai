"""
Prompt engineering for risk assessment agent.

Builds system and user prompts for Gemini-based clause evaluation.
"""

import logging
import json
from typing import Dict, List, Any

from src.agent_config import AgentConfig

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Builds prompts for risk assessment."""

    def __init__(self, config: AgentConfig):
        self.config = config

    @staticmethod
    def get_system_prompt() -> str:
        """Get system prompt for risk assessment."""
        return """You are an enterprise contract risk assessment agent.
            Your role is to help legal and procurement reviewers identify potentially risky contract language.

            You must:
            - evaluate only the clause text provided
            - use the supplied business rules as primary policy guidance
            - explain the result clearly and conservatively
            - avoid unsupported legal conclusions
            - return valid JSON only

            For each clause, classify as:
            - risk_flag: true or false
            - severity: Critical | High | Medium | Low | None

            You must include:
            - rule_id from the applicable rule
            - risk_category from the rule
            - confidence_score between 0 and 1
            - rationale explaining your assessment
            - evidence_text quoted exactly from the clause
            - recommended_action for remediation

            If the clause is not risky under the supplied rules, set risk_flag=false and severity=None.
            If ambiguous, set confidence_score lower and note the ambiguity in rationale.
            Do not invent policy requirements beyond the supplied rules."""

    def build_assessment_prompt(
        self, clause: Dict[str, Any], rules: List[Dict[str, Any]]
    ) -> str:
        """Build assessment prompt for a clause."""
        
        system_prompt = self.get_system_prompt()

        user_prompt = f"""Assess the following contract clause against the supplied business rules.

Contract metadata:
- contract_id: {clause.get('contract_id', 'unknown')}
- file_name: {clause.get('file_name', 'unknown')}
- document_type: {clause.get('document_type', 'unknown')}
- clause_id: {clause.get('clause_id', 'unknown')}
- clause_title: {clause.get('clause_title', 'unnamed')}

Clause text:
\"\"\"
{clause.get('clause_text', '')}
\"\"\"

Applicable business rules:
{json.dumps(self._format_rules_for_prompt(rules), indent=2)}

Return JSON with this schema:
{{
  "contract_id": "string",
  "clause_id": "string",
  "results": [
    {{
      "rule_id": "string",
      "risk_flag": true,
      "severity": "Critical|High|Medium|Low|None",
      "risk_category": "string",
      "confidence_score": 0.0,
      "rationale": "string",
      "evidence_text": "string excerpt from clause",
      "recommended_action": "string"
    }}
  ]
}}

If no rules apply, return results as an empty array."""

        return f"{system_prompt}\n\nUser Request:\n{user_prompt}"

    @staticmethod
    def _format_rules_for_prompt(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format rules for inclusion in prompt."""
        formatted = []

        for rule in rules:
            formatted.append(
                {
                    "rule_id": rule.get("rule_id"),
                    "rule_name": rule.get("rule_name"),
                    "rule_category": rule.get("rule_category"),
                    "rule_description": rule.get("rule_description"),
                    "risky_patterns": rule.get("risky_patterns", [])[:5],  # Top 5 patterns
                    "expected_condition": rule.get("expected_condition"),
                    "severity_default": rule.get("severity_default"),
                }
            )

        return formatted
