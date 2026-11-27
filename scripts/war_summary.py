"""Before/after tables for the Well-Architected write-up, from the raw red-team reports and probe files only.

    uv run python scripts/war_summary.py BEFORE_DIR AFTER_DIR > war/results.md

A row is an attacker failure when the attacker never produced its attack (CLI error, provider safeguard, or the
attacker declining): the library records those as evaluator errors scored 0.0 and counts them as breaches, so
they are split out here, as the talk did. A breach is a launched attack the judge failed (test_passes False).
"""

import json
import sys
from pathlib import Path


def rows(path: Path) -> list[dict]:
    d = json.loads(path.read_text())
    out = []
    for case, ok, score, reason in zip(d["cases"], d["test_passes"], d["scores"], d["reasons"], strict=True):
        failed_attacker = str(reason).startswith("An error occurred")
        out.append({"name": case["name"], "score": score, "attacker_failed": failed_attacker,
                    "breach": (not ok) and not failed_attacker})
    return out


def tally(rs: list[dict]) -> dict:
    launched = [r for r in rs if not r["attacker_failed"]]
    return {"attacks": len(rs), "attacker_failed": len(rs) - len(launched),
            "breaches": sum(r["breach"] for r in rs), "launched": len(launched),
            "public_ticket": [f"{r['name'].split('__')[1]} {r['score']:.2f}{' BREACH' if r['breach'] else ''}"
                              for r in rs if r["name"].startswith("stop_dev_public_ticket")],
            "breached_cases": sorted({r["name"] for r in rs if r["breach"]})}


def find(d: Path, attacker: str, label: str) -> Path:
    found = sorted(d.glob(f"evals/results/redteam-*-{attacker}-{label}-pass1.json"))
    if not found:
        raise SystemExit(f"no {attacker} {label} red-team report under {d}/evals/results")
    return found[-1]


def main() -> int:
    before, after = Path(sys.argv[1]), Path(sys.argv[2])
    print("| Attacker | Run | Attacks | Attacker failed | Launched | Breaches | stop_dev_public_ticket |")
    print("|---|---|---:|---:|---:|---:|---|")
    detail = []
    for attacker in ("daybreak", "mythos"):
        for label, root in (("before", before), ("after", after)):
            t = tally(rows(find(root, attacker, label)))
            print(f"| {attacker} | {label} | {t['attacks']} | {t['attacker_failed']} | {t['launched']} | "
                  f"{t['breaches']} | {'; '.join(t['public_ticket'])} |")
            detail.append(f"- {attacker} {label}: {', '.join(t['breached_cases']) or 'none'}")
    print("\nBreached attacks (case__strategy):\n" + "\n".join(detail))
    print("\n| Probe (model already fooled, public ticket CHG-2231) | Before | After |\n|---|---|---|")
    pb = {p["probe"]: p for p in json.loads((after / "war/probe-before.json").read_text())["probes"]}
    pa = {p["probe"]: p for p in json.loads((after / "war/probe-after.json").read_text())["probes"]}
    for name in [*pb, *[k for k in pa if k not in pb]]:
        def cell(p):
            if not p:
                return "n/a"
            return f"{p['instance']} {'STOPPED' if p['stopped'] else 'kept running'}"
        print(f"| {name} | {cell(pb.get(name))} | {cell(pa.get(name))} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
