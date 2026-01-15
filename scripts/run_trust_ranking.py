#!/usr/bin/env python3
"""
Run the reference trust ranking demo.

Example:
  python scripts/run_trust_ranking.py --top 10
"""

from __future__ import annotations

import argparse
import json
import logging, sys
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
from pathlib import Path

# Allow running from repo root without installing as a package
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from extensions.trust_ranking.reference_ranker import rank_agents  # noqa: E402
from extensions.trust_ranking.poc_policy import (  # noqa: E402
    apply_service_record_policy,
    EFFECTIVE_BAND_NEEDS_REVIEW,
)


def _recommended_top_ids(
    ranked: list[dict],
    effective_bands: dict[str, str] | None,
    n: int = 5,
) -> list[str]:
    out: list[str] = []
    for agent in ranked:
        agent_id = agent.get("id") or ""
        trust = agent.get("trust") or {}
        band = trust.get("effective_band", trust.get("band")) or "unknown"
        if effective_bands is not None:
            band = effective_bands.get(agent_id, band)
        if band == EFFECTIVE_BAND_NEEDS_REVIEW:
            continue
        out.append(agent_id)
        if len(out) >= n:
            break
    return out


def _load_agents(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    agents = data.get("agents")
    if not isinstance(agents, list):
        raise ValueError("Input JSON must contain an 'agents' list")
    return agents


def _load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Service record JSON must be an object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Trust ranking PoC runner (reference only)")
    parser.add_argument(
        "--input",
        default="examples/directory_sample.json",
        help="Path to JSON file containing {'agents': [...]}",
    )
    parser.add_argument(
        "--service-record",
        help="PoC-only: path to service_record__*.json artifact to apply policy overlay",
    )
    parser.add_argument("--top", type=int, default=10, help="How many results to print")
    parser.add_argument("--json", action="store_true", help="Output full ranked list as JSON")
    args = parser.parse_args()

    input_path = (REPO_ROOT / args.input).resolve()
    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        return 2

    try:
        agents = _load_agents(input_path)
        ranked = rank_agents(agents)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    service_record = None
    demotion_lines: list[str] = []
    effective_bands: dict[str, str] = {}
    if args.service_record:
        service_path = (REPO_ROOT / args.service_record).resolve()
        if not service_path.exists():
            print(f"ERROR: service record file not found: {service_path}", file=sys.stderr)
            return 2
        try:
            service_record = _load_json(service_path)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2

        for agent in ranked:
            agent_id = agent.get("id") or ""
            trust = agent.get("trust") or {}
            base_band = trust.get("band") or "unknown"
            base_score = trust.get("score", "n/a")
            effective_band, reasons = apply_service_record_policy(
                agent_id, base_band, service_record
            )
            trust["effective_band"] = effective_band
            trust["policy_reasons"] = reasons
            agent["trust"] = trust
            effective_bands[agent_id] = effective_band
            if effective_band == EFFECTIVE_BAND_NEEDS_REVIEW:
                reason_str = ", ".join(reasons) if reasons else "unspecified"
                demotion_lines.append(
                    "Demoted: "
                    f"{agent_id} base_score={base_score} base_band={base_band} "
                    f"-> effective_band={effective_band} reason={reason_str}"
                )

    if args.json:
        print(json.dumps({"agents": ranked}, indent=2, ensure_ascii=False))
        for line in demotion_lines:
            print(line, file=sys.stderr)
        return 0

    top_n = max(0, min(args.top, len(ranked)))

    print("Trust Ranking PoC (reference only)")
    print(f"Input: {args.input}")
    if args.service_record:
        print(f"Service record: {args.service_record}")
    print(f"Results: top {top_n} of {len(ranked)}")
    baseline_top5 = _recommended_top_ids(ranked, None, 5)
    with_record_top5 = _recommended_top_ids(ranked, effective_bands, 5)
    print(f"baseline recommended top5: {baseline_top5}")
    print(f"with_record recommended top5: {with_record_top5}")
    for line in demotion_lines:
        print(line)
    if service_record:
        recommended = []
        for agent in ranked:
            agent_id = agent.get("id") or ""
            trust = agent.get("trust") or {}
            band = trust.get("effective_band", trust.get("band")) or "unknown"
            band = effective_bands.get(agent_id, band)
            if band == EFFECTIVE_BAND_NEEDS_REVIEW:
                continue
            recommended.append(agent)
            if len(recommended) >= 5:
                break

        print("")
        print("Top 5 recommended")
        for i, agent in enumerate(recommended, start=1):
            name = agent.get("name") or agent.get("id") or "(unnamed)"
            agent_id = agent.get("id") or ""
            print(f"{i:>2}. {name} ({agent_id})")
    print("")

    for i, a in enumerate(ranked[:top_n], start=1):
        trust = a.get("trust") or {}
        score = trust.get("score", "n/a")
        band = trust.get("band", "n/a")
        reasons = trust.get("reasons", [])
        name = a.get("name") or a.get("id") or "(unnamed)"
        url = a.get("url") or ""

        reasons_str = "; ".join(reasons) if isinstance(reasons, list) else str(reasons)

        print(f"{i:>2}. {name}")
        print(f"    id: {a.get('id')}")
        print(f"   url: {url}")
        print(f" trust: {score} ({band})")
        print(f"reason: {reasons_str}")
        print("")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
