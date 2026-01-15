"""
PoC policy overlay for the trust ranking demo.

This does not change base scoring. It only computes an effective band
based on optional external service record descriptors.
"""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

from typing import Any

TRIGGER_DESCRIPTOR = "needs_escalation"
EFFECTIVE_BAND_NEEDS_REVIEW = "needs_review"


def _add_descriptors(raw: Any, out: list[str]) -> None:
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                out.append(item)
    elif isinstance(raw, str):
        out.append(raw)


def extract_descriptors(service_record: dict) -> set[str]:
    if not isinstance(service_record, dict):
        return set()

    collected: list[str] = []

    _add_descriptors(service_record.get("descriptors"), collected)
    _add_descriptors(service_record.get("descriptor"), collected)

    observations = service_record.get("observations")
    if isinstance(observations, list):
        for obs in observations:
            if not isinstance(obs, dict):
                continue
            _add_descriptors(obs.get("descriptors"), collected)
            _add_descriptors(obs.get("descriptor"), collected)

    return {d for d in collected if d}


def extract_descriptors_for_agent(service_record: dict, agent_id: str) -> set[str]:
    if not isinstance(service_record, dict) or not agent_id:
        return set()

    collected: list[str] = []

    def _norm(s: str) -> str:
        return "".join(ch for ch in s.lower() if ch.isalnum())

    def _matches_subject(candidate_id: str, subject_id: str) -> bool:
        if not candidate_id or not subject_id:
            return False
        # PoC heuristic: ignore hyphen/underscore and suffixes like "_ok".
        candidate = _norm(candidate_id).replace("ok", "")
        subject = _norm(subject_id)
        return candidate.startswith(subject) or subject in candidate

    subject_id = service_record.get("subject_agent_id") or service_record.get("subjectAgentId")
    if isinstance(subject_id, str) and _matches_subject(agent_id, subject_id):
        logger.info(
            "PoC mapping: subject_agent_id=%s -> directory agent_id=%s",
            subject_id, agent_id
        )
        for key in ("observations", "last_two_observations"):
            obs_list = service_record.get(key)
            if isinstance(obs_list, list):
                for obs in obs_list:
                    if not isinstance(obs, dict):
                        continue
                    _add_descriptors(obs.get("descriptors"), collected)
                    _add_descriptors(obs.get("descriptor"), collected)

    return {d for d in collected if d}


def apply_service_record_policy(
    agent_id: str,
    base_band: str,
    service_record: dict | None,
) -> tuple[str, list[str]]:
    if not service_record or not isinstance(service_record, dict):
        return base_band, []

    descriptors = extract_descriptors_for_agent(service_record, agent_id)
    if TRIGGER_DESCRIPTOR in descriptors:
        return EFFECTIVE_BAND_NEEDS_REVIEW, [TRIGGER_DESCRIPTOR]

    return base_band, []
