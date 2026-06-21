"""
Core risk assessment agent implementation supporting both:
1) API key mode via google.generativeai
2) ADC mode via Vertex AI
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import google.generativeai as genai
import vertexai
from google.cloud import bigquery
from vertexai.generative_models import GenerationConfig, GenerativeModel as VertexGenerativeModel

from src.agent_config import AgentConfig
from src.prompt_builder import PromptBuilder
from src.rule_engine import RuleEngine

logger = logging.getLogger(__name__)


class RiskAssessmentAgent:
    """ADK Agent for contract risk assessment."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.client = bigquery.Client(project=config.project_id)
        self.dataset = self.client.dataset(config.bq_dataset)
        self.rule_engine = RuleEngine(config)
        self.prompt_builder = PromptBuilder(config)
        self.run_batch_id = datetime.now(timezone.utc).strftime("agent-%Y%m%d-%H%M%S")

        self.auth_mode = (os.getenv("MODEL_AUTH_MODE", "adc") or "adc").strip().lower()
        self.api_model = None
        self.vertex_model = None

        if self.auth_mode == "api_key":
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY is required when MODEL_AUTH_MODE=api_key")
            genai.configure(api_key=api_key)
            self.api_model = genai.GenerativeModel(config.model_name)

        elif self.auth_mode == "adc":
            vertexai.init(project=config.project_id, location=config.location)
            self.vertex_model = VertexGenerativeModel(config.model_name)

        else:
            raise ValueError("MODEL_AUTH_MODE must be either 'api_key' or 'adc'")

    def run(self) -> Dict[str, Any]:
        """Execute risk assessment across all unassessed clauses."""
        logger.info("Starting risk assessment agent")

        results = {
            "contracts_assessed": 0,
            "clauses_evaluated": 0,
            "risks_flagged": 0,
            "critical_count": 0,
            "high_count": 0,
            "errors": [],
            "assessments": [],  
        }

        try:
            rules = self.rule_engine.get_enabled_rules()
            logger.info(f"Loaded {len(rules)} active rules")

            clauses = self._get_unassessed_clauses()
            logger.info(f"Found {len(clauses)} unassessed clauses")

            if not clauses:
                logger.info("No unassessed clauses found")
                return results

            assessed_contracts = set()
            for i in range(0, len(clauses), self.config.batch_size):
                batch = clauses[i : i + self.config.batch_size]

                for clause in batch:
                    try:
                        self._assess_clause(clause, rules, results)
                        assessed_contracts.add(clause["contract_id"])
                    except Exception as e:
                        logger.error(f"Error assessing clause {clause['clause_id']}: {e}")
                        results["errors"].append(
                            {
                                "clause_id": clause["clause_id"],
                                "error": str(e),
                            }
                        )

            results["contracts_assessed"] = len(assessed_contracts)

        except Exception as e:
            logger.error(f"Assessment pipeline failed: {e}", exc_info=True)
            results["errors"].append({"step": "pipeline", "error": str(e)})

        logger.info(
            f"Assessment complete: {results['clauses_evaluated']} evaluated, "
            f"{results['risks_flagged']} risks flagged"
        )

        return results

    def _get_unassessed_clauses(self) -> List[Dict[str, Any]]:
        """Retrieve clauses that haven't been assessed yet."""
        query = f"""
        SELECT
            c.clause_id,
            c.contract_id,
            c.clause_title,
            c.clause_text,
            c.page_number,
            c.section_name,
            ct.file_name,
            ct.document_type
        FROM `{self.config.project_id}.{self.config.bq_dataset}.contract_clauses` c
        JOIN `{self.config.project_id}.{self.config.bq_dataset}.contracts` ct
            ON c.contract_id = ct.contract_id
        WHERE NOT EXISTS (
            SELECT 1 FROM `{self.config.project_id}.{self.config.bq_dataset}.risk_assessments` a
            WHERE a.clause_id = c.clause_id
        )
        LIMIT {self.config.query_limit}
        """
        results = self.client.query(query).result()
        return [dict(row) for row in results]

    def _assess_clause(
        self, clause: Dict[str, Any], rules: List[Dict[str, Any]], results: Dict[str, Any]
    ) -> None:
        """Assess a single clause for risks."""
        logger.info(f"Assessing clause {clause['clause_id']}")

        applicable_rules = self.rule_engine.get_applicable_rules(
            clause.get("clause_text", ""), rules
        )

        if not applicable_rules:
            self._store_assessments(
                clause,
                {
                    "results": [
                        {
                            "rule_id": None,
                            "risk_flag": False,
                            "severity": "None",
                            "risk_category": "No Match",
                            "confidence_score": 1.0,
                            "rationale": "No enabled rule patterns matched this clause.",
                            "evidence_text": "",
                            "recommended_action": "No action required.",
                        }
                    ]
                },
                results,
            )
            results["clauses_evaluated"] += 1
            return
        #logger.info(f"Found {len(applicable_rules)} applicable rules for clause {clause['clause_id']}")
        prompt = self.prompt_builder.build_assessment_prompt(clause, applicable_rules)
        #logger.info(f"Assessment prompt for clause {clause['clause_id']}: {prompt}")
        response_text = self._generate_json_response(prompt)
        #logger.info(f"Model response: {response_text}")
        response_text = self._normalize_json_text(response_text)
        #assessment_data = json.loads(response_text)

        try:
            #logger.info(f"Model response for clause {clause['clause_id']}: {response_text}")
            assessment_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error("JSON parse failed for clause %s at pos %s. Raw model response: %s",
                          clause["clause_id"], e.pos, response_text)
            raise ValueError(f"Failed to parse JSON response: {e.msg}") from e 

        self._store_assessments(clause, assessment_data, results)
        results["clauses_evaluated"] += 1

    def _generate_json_response(self, prompt: str) -> str:
        """Generate JSON response using selected auth mode."""
        if self.auth_mode == "api_key":
            response = self.api_model.generate_content(
                prompt,
                generation_config={
                    "temperature": self.config.temperature,
                    #"max_output_tokens": self.config.max_tokens,
                    "response_mime_type": "application/json",
                },
            )
            return (response.text or "").strip()

        response = self.vertex_model.generate_content(
            prompt,
            generation_config=GenerationConfig(
                temperature=self.config.temperature,
                #max_output_tokens=self.config.max_tokens,
                response_mime_type="application/json",
            ),
        )
        return (response.text or "").strip()

    @staticmethod
    def _normalize_json_text(response_text: str) -> str:
        text = (response_text or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()
        return text

    def _store_assessments(
        self,
        clause: Dict[str, Any],
        assessment_data: Dict[str, Any],
        results: Dict[str, Any],
    ) -> None:
        """Store risk assessment results in BigQuery."""
        table = self.client.get_table(self.dataset.table("risk_assessments"))
        assessment_results = assessment_data.get("results", [])

        rows = []
        for result in assessment_results:
            if result.get("risk_flag"):
                results["risks_flagged"] += 1
                severity = result.get("severity", "Medium")
                if severity == "Critical":
                    results["critical_count"] += 1
                elif severity == "High":
                    results["high_count"] += 1
            else:
                severity = result.get("severity", "None")

            rows.append(
                {
                    "assessment_id": f"ASS-{uuid.uuid4().hex[:12].upper()}",
                    "contract_id": clause["contract_id"],
                    "clause_id": clause["clause_id"],
                    "rule_id": result.get("rule_id"),
                    "risk_flag": result.get("risk_flag", False),
                    "severity": severity,
                    "confidence_score": result.get("confidence_score", 0.0),
                    "rationale": result.get("rationale", ""),
                    "evidence_text": result.get("evidence_text", "")[:1000],
                    "recommended_action": result.get("recommended_action", ""),
                    "assessor_type": "ADK_AGENT",
                    "assessment_status": "COMPLETED",
                    "assessed_at": datetime.now(timezone.utc).isoformat(),
                    "model_name": self.config.model_name,
                    "batch_id": self.run_batch_id,
                }
            )

            # Collect summary entry for final report   
            results["assessments"].append({
                "clause_id": clause["clause_id"],
                "contract_id": clause["contract_id"],
                "rule_id": result.get("rule_id") or "N/A",
                "risk_category": result.get("risk_category", ""),
                "risk_flag": result.get("risk_flag", False),
                "severity": severity,
                "confidence_score": result.get("confidence_score", 0.0),
                "rationale": result.get("rationale", ""),
                "recommended_action": result.get("recommended_action", ""),
            })        

        if rows:
            errors = self.client.insert_rows_json(table, rows)
            if errors:
                logger.warning(f"Insert errors: {errors}")
            else:
                logger.debug(f"Stored {len(rows)} assessment results")