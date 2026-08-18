"""Project 1 (AI DevOps Assistant) integration bridge.

Provides API clients and data transformations for integrating
with Project 1's AI DevOps Agent.

Integration Points:
    - Knowledge Context API: Project 1's Agent retrieves context from Project 3
    - Incident Reporting: Project 1 sends incident data to Project 3
    - SOP Lookup: Project 1 queries SOPs from Project 3
"""

from typing import Any, Dict, List

from app.core.config import get_settings


class Project1Bridge:
    """Bridge for integrating with Project 1 (AI DevOps Assistant).

    Provides methods that Project 1's Agent can call to access
    knowledge, SOPs, and incident data from this system.

    This is the SERVER side of the integration - these methods
    are exposed via the /api/context/* endpoints and consumed
    by Project 1.
    """

    def __init__(self):
        self.settings = get_settings()

    @staticmethod
    def format_knowledge_context(
        topic: str,
        documents: List[Dict[str, Any]],
        sops: List[Dict[str, Any]],
        incidents: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Format knowledge context for Project 1's Agent.

        Args:
            topic: The topic being queried.
            documents: Relevant knowledge documents.
            sops: Relevant SOPs.
            incidents: Relevant incident records.

        Returns:
            Formatted context dict ready for Agent consumption.
        """
        return {
            "topic": topic,
            "summary": f"Found {len(documents)} documents, {len(sops)} SOPs, {len(incidents)} incidents",
            "knowledge": [
                {
                    "title": doc.get("title", ""),
                    "content": doc.get("content", "")[:500],  # Truncate for Agent context
                    "type": doc.get("doc_type", "general"),
                    "relevance": doc.get("relevance", 1.0),
                }
                for doc in documents[:5]  # Top 5 most relevant
            ],
            "sops": [
                {
                    "id": sop.get("id", ""),
                    "title": sop.get("title", ""),
                    "problem": sop.get("problem", ""),
                    "severity": sop.get("severity", ""),
                    "steps": sop.get("steps", []),
                }
                for sop in sops[:3]  # Top 3 SOPs
            ],
            "incidents": [
                {
                    "title": inc.get("title", ""),
                    "service": inc.get("service", ""),
                    "root_cause": inc.get("root_cause", ""),
                    "solution": inc.get("solution", ""),
                }
                for inc in incidents[:3]  # Top 3 incidents
            ],
        }

    @staticmethod
    def format_incident_from_agent(
        agent_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Format incident data received from Project 1's Agent.

        Project 1 sends incident data after an Agent execution fails
        or detects a problem. This method transforms it into the
        incident record format.

        Args:
            agent_data: Raw incident data from Project 1.

        Returns:
            Formatted incident record ready for storage.
        """
        return {
            "title": agent_data.get("title", "Unknown Incident"),
            "service": agent_data.get("service", "unknown"),
            "severity": agent_data.get("severity", "major"),
            "root_cause": agent_data.get("root_cause", ""),
            "solution": agent_data.get("solution", ""),
            "impact": agent_data.get("impact", ""),
            "timeline": agent_data.get("timeline", ""),
            "tags": agent_data.get("tags", []),
        }


class Project1APIClient:
    """Client for calling Project 1's APIs.

    Used when this service needs to trigger actions in Project 1,
    e.g. requesting an Agent analysis or querying monitoring data.
    """

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.project1_api_base.rstrip("/")
        self.api_key = self.settings.project1_api_key

    async def trigger_agent_analysis(self, topic: str) -> Dict[str, Any]:
        """Ask Project 1's Agent to analyze a topic.

        Args:
            topic: The topic or problem to analyze.

        Returns:
            Agent analysis result.
        """
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/agent/analyze",
                json={"topic": topic},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_alert_status(self) -> List[Dict[str, Any]]:
        """Get current alert status from Project 1.

        Returns:
            List of active alerts.
        """
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/alerts",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_system_health(self) -> Dict[str, Any]:
        """Get system health summary from Project 1.

        Returns:
            System health data.
        """
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/monitoring/summary",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
