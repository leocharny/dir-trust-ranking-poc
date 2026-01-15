import unittest

from extensions.trust_ranking.poc_policy import (
    apply_service_record_policy,
    EFFECTIVE_BAND_NEEDS_REVIEW,
)
from extensions.trust_ranking.reference_ranker import rank_agents


def _recommended_top5_ids(ranked: list[dict], service_record: dict | None) -> list[str]:
    recommended: list[str] = []
    for agent in ranked:
        agent_id = agent.get("id") or ""
        trust = agent.get("trust") or {}
        base_band = trust.get("band") or "unknown"
        effective_band, _ = apply_service_record_policy(
            agent_id, base_band, service_record
        )
        if effective_band == EFFECTIVE_BAND_NEEDS_REVIEW:
            continue
        recommended.append(agent_id)
        if len(recommended) >= 5:
            break
    return recommended


class TestPocPolicy(unittest.TestCase):
    def setUp(self):
        base_agent = {
            "url": "https://example.test",
            "capabilities": ["book"],
            "contact": "ops@example.test",
            "updated_at": "2025-12-28",
            "domain_verified": True,
            "key_present": True,
            "handshake_fail_ratio": 0.0,
            "rate_limit_violations": 0,
            "complaint_flags": 0,
        }
        names = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot"]
        self.agents = []
        for name in names:
            agent = dict(base_agent)
            agent["id"] = f"agent_{name.lower()}"
            agent["name"] = name
            agent["url"] = f"https://{name.lower()}.example.test"
            self.agents.append(agent)

        # Reverse order to ensure ranker sort drives top-5 ordering.
        self.agents.reverse()

    def test_top5_unchanged_without_service_record(self):
        ranked = rank_agents(self.agents)
        base_top5 = [agent["id"] for agent in ranked[:5]]
        recommended = _recommended_top5_ids(ranked, None)
        self.assertEqual(base_top5, recommended)

    def test_needs_escalation_excludes_agent_from_top5(self):
        ranked = rank_agents(self.agents)
        service_record = {
            "observations": [
                {
                    "agent_id": "agent_alpha",
                    "descriptors": ["needs_escalation"],
                }
            ]
        }
        recommended = _recommended_top5_ids(ranked, service_record)
        self.assertNotIn("agent_alpha", recommended)
        self.assertEqual(len(recommended), 5)
        self.assertEqual(
            recommended,
            [
                "agent_bravo",
                "agent_charlie",
                "agent_delta",
                "agent_echo",
                "agent_foxtrot",
            ],
        )


if __name__ == "__main__":
    unittest.main()
