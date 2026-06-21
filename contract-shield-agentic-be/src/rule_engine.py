"""
Rule engine for loading and managing business rules.

Retrieves risk rules from BigQuery and applies deterministic pattern matching.
"""

import logging
import re
from typing import Dict, List, Any, Optional

from google.cloud import bigquery

from src.agent_config import AgentConfig

logger = logging.getLogger(__name__)


class RuleEngine:
    """Manages and applies business risk rules."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.client = bigquery.Client(project=config.project_id)
        self.dataset = self.client.dataset(config.bq_dataset)
        self._rules_cache: Optional[List[Dict[str, Any]]] = None

    def get_enabled_rules(self) -> List[Dict[str, Any]]:
        """Get all enabled risk rules from BigQuery."""
        if self._rules_cache is not None:
            return self._rules_cache

        query = f"""
        SELECT
            rule_id,
            rule_name,
            rule_category,
            rule_description,
            risky_patterns,
            expected_condition,
            severity_default,
            enabled_flag
        FROM `{self.config.project_id}.{self.config.bq_dataset}.risk_rules`
        WHERE enabled_flag = true
        ORDER BY severity_default DESC, rule_id
        """

        try:
            results = self.client.query(query).result()
            self._rules_cache = [dict(row) for row in results]
            logger.info(f"Loaded {len(self._rules_cache)} rules from BigQuery")
            return self._rules_cache

        except Exception as e:
            logger.error(f"Failed to load rules: {e}")
            return []

    def apply_pattern_matching(self, clause_text: str, rule: Dict[str, Any]) -> bool:
        """Apply deterministic pattern matching for a rule."""
        patterns = rule.get("risky_patterns", [])

        if not patterns:
            return False

        # Normalize text for matching
        normalized_text = clause_text.lower()
        normalized_text = re.sub(r"\s+", " ", normalized_text)

        # Check if any pattern matches
        for pattern in patterns:
            if not pattern:
                continue

            # Escape and prepare pattern
            pattern_lower = pattern.lower().strip()
            if not pattern_lower:
                continue

            # Simple substring match (can be enhanced with regex)
            if pattern_lower in normalized_text:
                logger.debug(f"Pattern match: {pattern_lower[:50]}...")
                return True

        return False

    def get_applicable_rules(
        self, clause_text: str, rules: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Get rules applicable to a clause based on pattern matching."""
        applicable = []

        for rule in rules:
            if self.apply_pattern_matching(clause_text, rule):
                applicable.append(rule)

        return applicable
