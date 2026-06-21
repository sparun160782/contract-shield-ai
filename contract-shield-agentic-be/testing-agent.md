#To Run Script Python in The Terminal to find any errors
##-------------------------------------------------------------
```bash
python -c "from pathlib import Path; from dotenv import load_dotenv; load_dotenv(Path('.env')); load_dotenv(Path('.env.local'), override=True); from src.agent_config import AgentConfig; from src.network_trust import configure_system_trust; from src.risk_assessment_agent import RiskAssessmentAgent; configure_system_trust(); c=AgentConfig.from_env(); print(c); a=RiskAssessmentAgent(c); r=a.run(); [print(e) for e in r['errors']]"
```