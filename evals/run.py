"""Runs Gemma on the test sentences and scores both halves of the app.

    python -m evals.run                 # all dev sentences
    python -m evals.run --only d08 d11  # just some
    python -m evals.run --model gemma4:e4b

For each sentence:
  - model: did Gemma (plus the word dictionary) produce the expected tree operations?
  - code:  with Gemma's operations, did the app save / ask / reject as expected?
Every run is saved in evals/runs/ with Gemma's raw answers, so results can be compared later.
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import yaml

from backend import llm
from backend.planner import make_plan
from backend.seed import seed
from backend.tree import Tree, load_tree
from evals.scoring import expected_statuses, score_ops

ROOT = Path(__file__).resolve().parent.parent
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", default="dev", help="dev or holdout")
    parser.add_argument("--file", default=str(ROOT / "tests" / "sentences.yaml"))
    parser.add_argument("--only", nargs="*", help="case ids to run")
    parser.add_argument("--model", default=llm.MODEL)
    args = parser.parse_args()

    cases = yaml.safe_load(Path(args.file).read_text(encoding="utf-8"))[args.set]
    cases = [c for c in cases if c.get("sentence") and (not args.only or c["id"] in args.only)]

    villa_db = ROOT / "trees" / "_eval-villa-diodati.db"
    conn, _ = seed(ROOT / "data" / "villa-diodati.yaml", villa_db)
    villa = load_tree(conn)
    conn.close()

    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    out_dir = ROOT / "evals" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{stamp}-{args.set}-{args.model.replace(':', '_')}-{llm.PROMPT_VERSION}.jsonl"

    print(f"Model {args.model}, prompt {llm.PROMPT_VERSION}, {len(cases)} sentences\n")
    model_ok = code_ok = 0
    started = time.perf_counter()
    with out_path.open("w", encoding="utf-8") as log:
        for case in cases:
            result = llm.parse_sentence(case["sentence"], model=args.model)
            score = score_ops(case["expected_ops"], result["ops"], case.get("also_ok"))
            tree = villa if case["tree"] == "villa-diodati" else Tree()
            plan = make_plan(tree, result["ops"])
            expected_code = "/".join(sorted(expected_statuses(case["expect_code"])))
            code_pass = plan.status in expected_statuses(case["expect_code"])

            model_ok += score["ok"]
            code_ok += code_pass
            mark = lambda ok: "ok " if ok else "NO "  # noqa: E731
            print(f"{case['id']}  model {mark(score['ok'])} code {mark(code_pass)} ({plan.status:6}) {result['seconds']:>5}s  {case['sentence']}")
            for m in score["missing"]:
                print(f"       missing: {m}")
            for e in score["extra"]:
                print(f"       extra:   {e}")
            for p in result["problems"]:
                print(f"       unusable: {p}")
            if not score["ok"]:
                for op in result["model_ops"]:
                    print(f"       gemma:   {op}")
            if not code_pass:
                asked = [q.get("name") or q.get("word") for q in plan.questions]
                print(f"       code expected {expected_code}; errors {plan.errors}; asked {asked}")

            log.write(json.dumps({
                "id": case["id"], "sentence": case["sentence"], "model": args.model,
                "prompt": llm.PROMPT_VERSION, "seconds": result["seconds"],
                "raw": result["raw"], "model_ops": result["model_ops"], "ops": result["ops"], "problems": result["problems"],
                "model_ok": score["ok"], "missing": score["missing"], "extra": score["extra"],
                "code_status": plan.status, "code_expected": expected_code, "code_ok": code_pass,
                "errors": plan.errors, "questions": plan.questions,
            }, ensure_ascii=False) + "\n")

    total = len(cases)
    minutes = (time.perf_counter() - started) / 60
    print(f"\nModel: {model_ok}/{total} sentences fully right")
    print(f"Code:  {code_ok}/{total} sentences with the right save/ask/reject")
    print(f"Time:  {minutes:.1f} min. Log: {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
