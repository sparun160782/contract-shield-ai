"""
ADK Agent Backend for Contract Risk Assessment.

This module implements the risk assessment agent that:
1. Retrieves contract clauses from BigQuery
2. Loads applicable business rules
3. Evaluates clauses using LLM reasoning
4. Classifies risks and generates recommendations
5. Stores assessment results in BigQuery
"""

import os
import sys
import logging
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

LAYMAN_BY_RULE = {
    "R001": "Contract may auto-renew unless cancelled early.",
    "R002": "Liability may be uncapped; potential financial exposure is very high.",
    "R003": "Termination rights may be imbalanced between supplier and customer.",
    "R004": "Confidentiality protection may be too narrow or too short.",
    "R005": "Personal data transfers may be too broad and weakly controlled.",
    "R006": "Security obligations are too discretionary and hard to enforce.",
    "R007": "Breach notification timeline may be too slow.",
    "R008": "Audit rights are restricted; oversight is limited.",
    "R009": "Data retention may be too broad or indefinite.",
    "R010": "Governing law may need policy approval.",
    "N/A": "No specific risk rule applied.",
}


def why_severity(risk_flag: bool, severity: str) -> str:
    if not risk_flag:
        return "Pattern matched but context appears acceptable for this clause."
    if severity == "Critical":
        return "Serious legal/commercial exposure; urgent action needed."
    if severity == "High":
        return "Material risk likely requiring negotiation."
    if severity == "Medium":
        return "Important gap; should be improved."
    if severity == "Low":
        return "Policy-check item; usually not a deal blocker."
    return "No actionable risk identified."


def print_assessment_table(assessments: list[dict]) -> None:
    if not assessments:
        return

    headers = ["Clause", "Rule", "Severity", "Layman Meaning", "Why this severity"]
    rows = []
    for a in assessments:
        rule_id = a.get("rule_id") or "N/A"
        severity = a.get("severity", "None")
        risk_flag = bool(a.get("risk_flag", False))
        rows.append([
            a.get("clause_id", ""),
            rule_id,
            severity,
            LAYMAN_BY_RULE.get(rule_id, "Rule matched; review rationale."),
            why_severity(risk_flag, severity),
        ])

    # Compute column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, col in enumerate(row):
            widths[i] = max(widths[i], len(str(col)))

    def fmt_row(cols):
        return " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(cols))

    sep = "-+-".join("-" * w for w in widths)

    print("\n" + "=" * len(fmt_row(headers)))
    print("CONTRACT RISK ASSESSMENT TABLE")
    print("=" * len(fmt_row(headers)))
    print(fmt_row(headers))
    print(sep)
    for row in rows:
        print(fmt_row(row))


def main():
    """Entry point for ADK agent backend."""
    logger.info("Contract Risk Assessment Agent - Starting")
    
    # Import here to allow graceful initialization
    try:
        from src.agent_config import AgentConfig
        from src.network_trust import configure_system_trust
        from src.risk_assessment_agent import RiskAssessmentAgent
    except ImportError as e:
        logger.error(f"Failed to import agent modules: {e}")
        logger.info("Note: Run 'make install' to set up dependencies")
        return 1

    try:
        configure_system_trust()
        config = AgentConfig.from_env()
        config.validate()
        
        agent = RiskAssessmentAgent(config)
        results = agent.run()

        print_assessment_table(results.get("assessments", []))
        
         # Print detailed assessment report
        assessments = results.get("assessments", [])
        if assessments:
            SEVERITY_LABEL = {
                "Critical": "🔴 Critical",
                "High":     "🟠 High    ",
                "Medium":   "🟡 Medium  ",
                "Low":      "🔵 Low     ",
                "None":     "⚪ None    ",
            }
            RISK_FLAG_LABEL = {True: "YES ⚠", False: "NO  ✓"}

            print("\n" + "=" * 70)
            print("CONTRACT RISK ASSESSMENT DETAILS")
            print("=" * 70)
            for i, a in enumerate(assessments, 1):
                flag   = a.get("risk_flag", False)
                sev    = a.get("severity", "None")
                rule   = a.get("rule_id", "N/A")
                cat    = a.get("risk_category", "")
                rat    = a.get("rationale", "")
                action = a.get("recommended_action", "")
                conf   = a.get("confidence_score", 0.0)

                # Wrap long text at 65 chars
                def wrap(text, width=65):
                    words, lines, line = text.split(), [], ""
                    for w in words:
                        if len(line) + len(w) + 1 > width:
                            lines.append(line)
                            line = w
                        else:
                            line = (line + " " + w).strip()
                    if line:
                        lines.append(line)
                    return ("\n" + " " * 18).join(lines)

                print(f"\n[{i:02d}] Clause   : {a.get('clause_id', '')}")
                print(f"     Rule     : {rule}  |  {cat}")
                print(f"     Severity : {SEVERITY_LABEL.get(sev, sev)}  |  Risk Flag: {RISK_FLAG_LABEL.get(flag, str(flag))}  |  Confidence: {conf:.2f}")
                print(f"     Rationale: {wrap(rat)}")
                print(f"     Action   : {wrap(action)}")
                print("     " + "-" * 65)

        # Print summary
        print("\n" + "=" * 70)
        print("RISK ASSESSMENT AGENT SUMMARY")
        print("=" * 70)
        print(f"Contracts Assessed:  {results.get('contracts_assessed', 0)}")
        print(f"Clauses Evaluated:   {results.get('clauses_evaluated', 0)}")
        print(f"Risks Flagged:       {results.get('risks_flagged', 0)}")
        print(f"Critical Severity:   {results.get('critical_count', 0)}")
        print(f"High Severity:       {results.get('high_count', 0)}")
        print(f"Errors:              {len(results.get('errors', []))}")
        print("=" * 70)
        
        return 0 if len(results.get('errors', [])) == 0 else 1
    

        
    except Exception as e:
        logger.error(f"Agent execution failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
