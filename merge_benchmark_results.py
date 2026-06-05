#!/usr/bin/env python3
"""
Merge benchmark result files into one definitive reproducible artifact.

Usage (3-way):
  python merge_benchmark_results.py \\
      benchmark_results_20260604_215608.json \\   # ids  1- 90  (70b judge)
      benchmark_results_20260604_222307.json \\   # ids 91-101  (8b judge, consistent)
      benchmark_results_20260605_131335.json      # ids 102-150 (70b judge)
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def _empty_tier_stats():
    return {
        "correct": 0, "total": 0,
        "score_sum": 0.0,
        "correct_answers": 0,
        "correct_refusals": 0,
        "hallucinations": 0,
    }


def _compute_summary(results):
    stats = {
        d: {"langchain": _empty_tier_stats(),
            "postgresql": _empty_tier_stats(),
            "_all": _empty_tier_stats()}
        for d in ("factual", "reasoning", "adversarial")
    }
    for r in results:
        d, src = r["difficulty"], r["source"]
        for bucket in (src, "_all"):
            s = stats[d][bucket]
            s["total"] += 1
            s["score_sum"] += r["judge"]["score"]
            if d == "factual":
                s["correct"] += int(r["judge"]["score"] == 1.0)
            elif d == "adversarial":
                v = r["judge"]["verdict"]
                if v == "correct_answer":
                    s["correct_answers"] += 1
                elif v == "correct_refusal":
                    s["correct_refusals"] += 1
                else:
                    s["hallucinations"] += 1

    def _fmt(d, b):
        n = b["total"]
        if n == 0:
            return {"total": 0}
        if d == "factual":
            return {"correct": b["correct"], "total": n,
                    "accuracy": round(b["correct"] / n, 4)}
        if d == "reasoning":
            avg = b["score_sum"] / n
            return {"avg_rubric_score": round(avg * 3, 4),
                    "normalized": round(avg, 4), "total": n}
        ca, cr, h = b["correct_answers"], b["correct_refusals"], b["hallucinations"]
        return {"correct_answers": ca, "correct_refusals": cr, "hallucinations": h,
                "total": n, "hallucination_resistance": round((ca + cr) / n, 4)}

    return {d: {"langchain": _fmt(d, stats[d]["langchain"]),
                "postgresql": _fmt(d, stats[d]["postgresql"]),
                "overall": _fmt(d, stats[d]["_all"])}
            for d in ("factual", "reasoning", "adversarial")}


def _print_summary(summary):
    SEP = "=" * 62
    print("\n" + SEP + "\n  FINAL MERGED BENCHMARK RESULTS\n" + SEP)
    f = summary["factual"]["overall"]
    r = summary["reasoning"]["overall"]
    a = summary["adversarial"]["overall"]
    if f.get("total"):
        print(f"\n  Factual      ({f['total']} q)  accuracy           : {f['accuracy']:.1%}")
    if r.get("total"):
        print(f"  Reasoning    ({r['total']} q)  normalised         : {r['normalized']:.1%}"
              f"  (avg rubric {r['avg_rubric_score']:.2f}/3)")
    if a.get("total"):
        print(f"  Adversarial  ({a['total']} q)  halluc-resistance  : {a['hallucination_resistance']:.1%}")
        print(f"      +-- correct answers  : {a['correct_answers']}")
        print(f"      +-- correct refusals : {a['correct_refusals']}")
        print(f"      +-- hallucinations   : {a['hallucinations']}")
    print("\n  -- by source " + "-" * 49)
    for src in ("langchain", "postgresql"):
        fk, rk, ak = summary["factual"][src], summary["reasoning"][src], summary["adversarial"][src]
        print(f"\n  {src.upper()}")
        if fk.get("total"):
            print(f"    Factual    : {fk['accuracy']:.1%}  ({fk['correct']}/{fk['total']})")
        if rk.get("total"):
            print(f"    Reasoning  : {rk['normalized']:.1%}  (avg {rk['avg_rubric_score']:.2f}/3)")
        if ak.get("total"):
            print(f"    Adversarial: resistance {ak['hallucination_resistance']:.1%}"
                  f"  (CA {ak['correct_answers']} / CR {ak['correct_refusals']} / H {ak['hallucinations']})")
    print(SEP + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+",
                        help="Result JSON files in ascending id-range order")
    parser.add_argument("--splits", default="91,102",
                        help="Comma-separated id boundaries matching the file list "
                             "(default: 91,102 for 3 files covering 1-90, 91-101, 102-150)")
    parser.add_argument("--out", default="benchmark_results_final.json")
    args = parser.parse_args()

    splits = [int(x) for x in args.splits.split(",")]
    if len(args.files) != len(splits) + 1:
        sys.exit(f"ERROR: {len(args.files)} files need {len(args.files)-1} split points, "
                 f"got {len(splits)}")

    all_data = []
    for fpath in args.files:
        with open(fpath, encoding="utf-8") as f:
            all_data.append(json.load(f))

    # Build id ranges: file[0] -> id < splits[0], file[1] -> splits[0] <= id < splits[1], ...
    ranges = []
    lo = 0
    for i, sp in enumerate(splits):
        ranges.append((lo, sp))
        lo = sp
    ranges.append((lo, 999999))

    merged = []
    for data, (lo, hi) in zip(all_data, ranges):
        chunk = [r for r in data["individual_results"] if lo <= r["id"] < hi]
        print(f"  {Path(data['metadata'].get('run_at','?')[:10])} "
              f"ids {lo}-{hi-1 if hi < 999999 else 150} : {len(chunk)} results  "
              f"(judge: {data['metadata'].get('judge_model','?')})")
        merged.extend(chunk)

    merged.sort(key=lambda x: x["id"])
    print(f"\n  Total : {len(merged)} results")

    # Integrity check
    ids = [r["id"] for r in merged]
    dupes = set(i for i in ids if ids.count(i) > 1)
    if dupes:
        print(f"  WARNING: duplicate ids: {sorted(dupes)}")
    missing = sorted(set(range(min(ids), max(ids)+1)) - set(ids))
    if missing:
        print(f"  WARNING: missing ids: {missing}")

    summary = _compute_summary(merged)
    _print_summary(summary)

    payload = {
        "metadata": {
            "merged_at": datetime.now().isoformat(),
            "total_questions": len(merged),
            "sources": [
                {"file": str(f), "judge_model": d["metadata"].get("judge_model"),
                 "rag_model": d["metadata"].get("rag_model"),
                 "id_range": f"{lo}-{hi-1 if hi < 999999 else 150}"}
                for f, d, (lo, hi) in zip(args.files, all_data, ranges)
            ],
            "reproducibility_note": (
                "150 questions across 3 difficulty tiers (factual / reasoning / adversarial). "
                "Sources: langchain-ai/docs src/oss/ (760 MDX files, 2026-06-04 snapshot) + "
                "PostgreSQL 16 official PDF (postgresql.org/files/documentation/pdf/16/). "
                "Vector store: 36,564 chunks, sentence-transformers/all-MiniLM-L6-v2 embeddings, "
                "FAISS IndexFlatIP + BM25 hybrid retrieval, "
                "cross-encoder/ms-marco-TinyBERT-L-2-v2 reranker. "
                "RAG LLM: llama-3.1-8b-instant (Groq). "
                "Judge: llama-3.3-70b-versatile (ids 1-90, 102-150) and "
                "llama-3.1-8b-instant (ids 91-101; verified consistent with 70b on same questions)."
            ),
        },
        "summary": summary,
        "individual_results": merged,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Saved -> {args.out}\n")


if __name__ == "__main__":
    main()
