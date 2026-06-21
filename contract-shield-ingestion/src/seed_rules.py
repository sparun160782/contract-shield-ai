"""Seed risk rules from YAML into BigQuery."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml
from google.cloud import bigquery

from src.config import Config
from src.network_trust import configure_system_trust

logger = logging.getLogger(__name__)


def _default_rules_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "risk_rules.yaml"
    )


def _load_rules(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        payload = yaml.safe_load(fh) or {}
    return payload.get("rules", [])


def _merge_rule(client: bigquery.Client, config: Config, rule: Dict[str, Any]) -> None:
    table = f"`{config.project_id}.{config.bq_dataset}.risk_rules`"
    now_ts = datetime.now(timezone.utc)

    query = f"""
    MERGE {table} AS T
    USING (
      SELECT
        @rule_id AS rule_id,
        @rule_name AS rule_name,
        @rule_category AS rule_category,
        @rule_description AS rule_description,
        @risky_patterns AS risky_patterns,
        @expected_condition AS expected_condition,
        @severity_default AS severity_default,
        @enabled_flag AS enabled_flag,
        @rule_version AS rule_version,
        @now_ts AS now_ts
    ) AS S
    ON T.rule_id = S.rule_id
    WHEN MATCHED THEN UPDATE SET
      rule_name = S.rule_name,
      rule_category = S.rule_category,
      rule_description = S.rule_description,
      risky_patterns = S.risky_patterns,
      expected_condition = S.expected_condition,
      severity_default = S.severity_default,
      enabled_flag = S.enabled_flag,
      rule_version = S.rule_version,
      updated_at = S.now_ts
    WHEN NOT MATCHED THEN INSERT (
      rule_id,
      rule_name,
      rule_category,
      rule_description,
      risky_patterns,
      expected_condition,
      severity_default,
      enabled_flag,
      rule_version,
      created_at,
      updated_at
    ) VALUES (
      S.rule_id,
      S.rule_name,
      S.rule_category,
      S.rule_description,
      S.risky_patterns,
      S.expected_condition,
      S.severity_default,
      S.enabled_flag,
      S.rule_version,
      S.now_ts,
      S.now_ts
    )
    """

    params = [
        bigquery.ScalarQueryParameter("rule_id", "STRING", rule.get("rule_id")),
        bigquery.ScalarQueryParameter("rule_name", "STRING", rule.get("rule_name")),
        bigquery.ScalarQueryParameter("rule_category", "STRING", rule.get("rule_category")),
        bigquery.ScalarQueryParameter("rule_description", "STRING", rule.get("rationale_template", "")),
        bigquery.ArrayQueryParameter("risky_patterns", "STRING", rule.get("risky_patterns", [])),
        bigquery.ScalarQueryParameter("expected_condition", "STRING", rule.get("expected_condition", "")),
        bigquery.ScalarQueryParameter("severity_default", "STRING", rule.get("severity_default", "Medium")),
        bigquery.ScalarQueryParameter("enabled_flag", "BOOL", True),
        bigquery.ScalarQueryParameter("rule_version", "STRING", "v1"),
        bigquery.ScalarQueryParameter("now_ts", "TIMESTAMP", now_ts),
    ]

    client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    configure_system_trust()

    parser = argparse.ArgumentParser(description="Seed risk rules into BigQuery")
    parser.add_argument("--rules-file", type=str, default=str(_default_rules_path()))
    args = parser.parse_args()

    config = Config.from_env()
    rules_file = Path(args.rules_file)

    if not rules_file.exists():
        logger.error("Rules file not found: %s", rules_file)
        return 1

    rules = _load_rules(rules_file)
    if not rules:
        logger.warning("No rules found in %s", rules_file)
        return 0

    client = bigquery.Client(project=config.project_id)
    for rule in rules:
        _merge_rule(client, config, rule)

    logger.info("Seeded %d rules into %s.%s.risk_rules", len(rules), config.project_id, config.bq_dataset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
