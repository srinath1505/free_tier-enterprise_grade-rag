#!/usr/bin/env python3
"""
RAG Benchmark Runner - 150 questions, 3 difficulty tiers.

Metrics
-------
  factual     : % correct  (binary CORRECT / INCORRECT)
  reasoning   : normalised 0-1 from 0-3 rubric
  adversarial : hallucination_resistance = (correct_answers + correct_refusals) / total
                (tracks what no standard RAGAS metric captures)

Usage
-----
  python benchmark_runner.py
  python benchmark_runner.py --skip-ingest           # reuse existing benchmark_vector_store/
  python benchmark_runner.py --limit 2               # smoke test with first 2 questions
  python benchmark_runner.py --out results/run1.json
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from datetime import datetime
from typing import Any

# Override paths BEFORE any backend import (pydantic-settings reads env at
# Settings() instantiation which happens at import time).
ROOT = pathlib.Path(__file__).parent
BENCHMARK_VS = str(ROOT / "benchmark_vector_store")
os.environ["VECTOR_STORE_PATH"] = BENCHMARK_VS
os.environ.setdefault("LLM_PROVIDER", "groq")
os.environ.setdefault("GROQ_MODEL", "llama-3.1-8b-instant")

sys.path.insert(0, str(ROOT))

import requests  # noqa: E402

from backend.core.config import settings  # noqa: E402
from backend.engine.reranker import Reranker  # noqa: E402
from backend.engine.retriever import HybridRetriever  # noqa: E402
from backend.engine.vector_store import VectorStore  # noqa: E402
from ingestion.chunker import SemanticChunker  # noqa: E402
from ingestion.loaders.pdf import PDFLoader  # noqa: E402
from ingestion.loaders.txt import TXTLoader  # noqa: E402

# -----------------------------------------------------------------------------
LANGCHAIN_DIR  = ROOT / "benchmark_docs" / "langchain"
POSTGRESQL_PDF = ROOT / "benchmark_docs" / "postgresql" / "postgresql-16-docs.pdf"
QUESTIONS_FILE = ROOT / "rag_benchmark_questions.json"
GROQ_URL       = "https://api.groq.com/openai/v1/chat/completions"
JUDGE_MODEL    = "llama-3.3-70b-versatile"

RAG_SYSTEM_PROMPT = (
    "You are a precise technical assistant. Answer the question using ONLY the provided context.\n"
    "If the answer is not present in the context, respond with exactly: "
    "\"I don't have enough information in the provided documents to answer this question.\"\n"
    "Be concise and factual. Do not speculate or add information not in the context."
)

# -----------------------------------------------------------------------------
# 1. INGEST
# -----------------------------------------------------------------------------

def ingest_benchmark_docs() -> VectorStore:
    print("\n-- Ingesting benchmark docs ------------------------------------")

    raw_docs: list[dict] = []

    # LangChain: all .md / .mdx files, recursively
    mdx_files = sorted(LANGCHAIN_DIR.rglob("*.mdx")) + sorted(LANGCHAIN_DIR.rglob("*.md"))
    print(f"  LangChain: {len(mdx_files)} MDX/MD files ...", flush=True)
    for i, fpath in enumerate(mdx_files, 1):
        if i % 100 == 0:
            print(f"    loaded {i}/{len(mdx_files)}", flush=True)
        docs = TXTLoader(str(fpath)).load()
        for d in docs:
            d["metadata"]["type"] = "langchain_mdx"
        raw_docs.extend(docs)

    # PostgreSQL: PDF
    print(f"  PostgreSQL: {POSTGRESQL_PDF.name} ...", flush=True)
    raw_docs.extend(PDFLoader(str(POSTGRESQL_PDF)).load())

    print(f"  Loaded {len(raw_docs)} source documents.")

    print("  Chunking ...", flush=True)
    chunks = SemanticChunker().chunk(raw_docs)
    print(f"  {len(chunks)} chunks created.")

    print("  Embedding & storing ...", flush=True)
    vs = VectorStore()
    texts = [c["content"] for c in chunks]
    metas = [{**c["metadata"], "content": c["content"]} for c in chunks]
    vs.add_documents(texts, metas)
    print(f"  Saved -> {BENCHMARK_VS}")
    return vs


# -----------------------------------------------------------------------------
# 2. RAG PIPELINE
# -----------------------------------------------------------------------------

def _groq_generate(prompt: str, system: str, model: str, api_key: str,
                   max_tokens: int = 512, temperature: float = 0.3,
                   max_retries: int = 6) -> str:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    for attempt in range(max_retries):
        try:
            r = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={"model": model, "messages": messages,
                      "max_tokens": max_tokens, "temperature": temperature},
                timeout=60,
            )
            if r.status_code == 429:
                wait = min(2 ** attempt, 64)
                print(f"    [rate-limit {model}] waiting {wait}s ...", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout):
            if attempt == max_retries - 1:
                raise
            wait = min(2 ** attempt, 32)
            time.sleep(wait)
    return "ERROR: max retries exceeded"


def run_rag(question: str, retriever: HybridRetriever, reranker: Reranker,
            api_key: str, rag_model: str) -> dict[str, Any]:
    docs = retriever.search(question, k=5)
    docs = reranker.rerank(question, docs, top_k=3)

    if not docs:
        return {
            "answer": "I don't have enough information in the provided documents to answer this question.",
            "context": "",
            "sources": [],
        }

    context = "\n\n---\n\n".join(d.get("content", "") for d in docs)
    answer = _groq_generate(
        prompt=question,
        system=RAG_SYSTEM_PROMPT + f"\n\nContext:\n{context[:6000]}",
        model=rag_model,
        api_key=api_key,
    )
    return {"answer": answer, "context": context,
            "sources": [d.get("source", "") for d in docs]}


# -----------------------------------------------------------------------------
# 3. JUDGE
# -----------------------------------------------------------------------------

def _judge_call(prompt: str, api_key: str) -> str:
    return _groq_generate(
        prompt=prompt, system="", model=JUDGE_MODEL,
        api_key=api_key, max_tokens=300, temperature=0.0,
    )


def judge_factual(question: str, context: str, answer: str, api_key: str) -> dict:
    raw = _judge_call(
        f"""Evaluate a RAG system answer to a factual question.

QUESTION: {question}

RETRIEVED CONTEXT:
{context[:2500]}

SYSTEM ANSWER: {answer}

Is the answer CORRECT or INCORRECT?
CORRECT = accurately addresses the question.
INCORRECT = wrong, misleading, or the system refused to answer a clearly answerable question.

First line: exactly CORRECT or INCORRECT
Second line: one-sentence reason (max 20 words).""",
        api_key,
    )
    lines = raw.strip().splitlines()
    verdict = "CORRECT" if lines and "CORRECT" in lines[0].upper() else "INCORRECT"
    return {"verdict": verdict, "score": 1.0 if verdict == "CORRECT" else 0.0, "raw": raw}


def judge_reasoning(question: str, context: str, answer: str, api_key: str) -> dict:
    raw = _judge_call(
        f"""Evaluate a RAG system answer to a reasoning/conceptual question.

QUESTION: {question}

RETRIEVED CONTEXT:
{context[:2500]}

SYSTEM ANSWER: {answer}

Score 0-3:
3 = Complete, accurate, covers all key aspects
2 = Mostly correct, minor gaps
1 = Partially correct, misses major points
0 = Wrong, empty, or refused an answerable question

First line: exactly SCORE: <0|1|2|3>
Second line: one-sentence justification (max 20 words).""",
        api_key,
    )
    score_val = 0
    for line in raw.splitlines():
        if "SCORE:" in line.upper():
            try:
                score_val = int(line.upper().split("SCORE:")[-1].strip()[0])
                score_val = max(0, min(3, score_val))
            except (IndexError, ValueError):
                pass
            break
    return {"verdict": f"SCORE:{score_val}", "score": score_val / 3.0, "raw": raw}


def judge_adversarial(question: str, context: str, answer: str, api_key: str) -> dict:
    raw = _judge_call(
        f"""Evaluate a RAG system response to an adversarial question that tests hallucination resistance.

QUESTION: {question}

RETRIEVED CONTEXT (what the system had access to):
{context[:2500]}

SYSTEM ANSWER: {answer}

Step 1 - Is the specific answer to this question present or derivable from the context above? (YES / NO)
Step 2 - Based on step 1:
  * YES, context has the answer -> did the system give a CORRECT answer or HALLUCINATE (wrong/invented)?
  * NO, context lacks the answer -> did the system correctly REFUSE ("I don't know") or HALLUCINATE (fabricated answer)?

First line: exactly one of:
  CORRECT_ANSWER    (context had it; system answered correctly)
  HALLUCINATION     (system invented or got wrong)
  CORRECT_REFUSAL   (context lacked it; system correctly declined)
Second line: one-sentence justification (max 20 words).""",
        api_key,
    )
    first = raw.splitlines()[0].upper() if raw.splitlines() else ""
    if "CORRECT_REFUSAL" in first or ("REFUSAL" in first and "CORRECT" in first):
        verdict, score = "correct_refusal", 1.0
    elif "CORRECT_ANSWER" in first or ("CORRECT" in first and "ANSWER" in first):
        verdict, score = "correct_answer", 1.0
    elif "HALLUCIN" in first:
        verdict, score = "hallucination", 0.0
    else:
        # Conservative fallback: treat ambiguous as hallucination
        verdict, score = "hallucination", 0.0
    return {"verdict": verdict, "score": score, "raw": raw}


JUDGE_FN = {
    "factual":    judge_factual,
    "reasoning":  judge_reasoning,
    "adversarial": judge_adversarial,
}


# -----------------------------------------------------------------------------
# 4. METRICS AGGREGATION
# -----------------------------------------------------------------------------

def _empty_tier_stats() -> dict:
    return {
        "correct": 0, "total": 0,
        "score_sum": 0.0,
        "correct_answers": 0,
        "correct_refusals": 0,
        "hallucinations": 0,
    }


def _compute_summary(results: list[dict]) -> dict:
    stats: dict[str, dict[str, dict]] = {
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

    def _format(d: str, bucket: dict) -> dict:
        n = bucket["total"]
        if n == 0:
            return {"total": 0}
        if d == "factual":
            return {"correct": bucket["correct"], "total": n,
                    "accuracy": round(bucket["correct"] / n, 4)}
        if d == "reasoning":
            avg = bucket["score_sum"] / n
            return {"avg_rubric_score": round(avg * 3, 4),
                    "normalized": round(avg, 4), "total": n}
        ca  = bucket["correct_answers"]
        cr  = bucket["correct_refusals"]
        h   = bucket["hallucinations"]
        res = (ca + cr) / n if n else 0
        return {
            "correct_answers": ca, "correct_refusals": cr,
            "hallucinations": h, "total": n,
            "hallucination_resistance": round(res, 4),
        }

    summary = {}
    for d in ("factual", "reasoning", "adversarial"):
        summary[d] = {
            "langchain":  _format(d, stats[d]["langchain"]),
            "postgresql": _format(d, stats[d]["postgresql"]),
            "overall":    _format(d, stats[d]["_all"]),
        }
    return summary


# -----------------------------------------------------------------------------
# 5. PRINT REPORT
# -----------------------------------------------------------------------------

def _print_report(summary: dict, elapsed: float) -> None:
    SEP = "=" * 62
    print("\n" + SEP)
    print("  RAG BENCHMARK RESULTS")
    print(SEP)

    f = summary["factual"]["overall"]
    r = summary["reasoning"]["overall"]
    a = summary["adversarial"]["overall"]

    if f.get("total", 0):
        print(f"\n  Factual      ({f['total']} q)  accuracy           : {f['accuracy']:.1%}")
    if r.get("total", 0):
        print(f"  Reasoning    ({r['total']} q)  normalised         : {r['normalized']:.1%}"
              f"  (avg rubric {r['avg_rubric_score']:.2f}/3)")
    if a.get("total", 0):
        ha = a["hallucination_resistance"]
        print(f"  Adversarial  ({a['total']} q)  halluc-resistance  : {ha:.1%}")
        print(f"      +-- correct answers  : {a['correct_answers']}")
        print(f"      +-- correct refusals : {a['correct_refusals']}")
        print(f"      +-- hallucinations   : {a['hallucinations']}")

    print("\n  -- by source " + "-" * 49)
    for src in ("langchain", "postgresql"):
        fk = summary["factual"][src]
        rk = summary["reasoning"][src]
        ak = summary["adversarial"][src]
        print(f"\n  {src.upper()}")
        if fk.get("total", 0):
            print(f"    Factual    : {fk['accuracy']:.1%}  ({fk['correct']}/{fk['total']})")
        if rk.get("total", 0):
            print(f"    Reasoning  : {rk['normalized']:.1%}  (avg {rk['avg_rubric_score']:.2f}/3)")
        if ak.get("total", 0):
            print(f"    Adversarial: resistance {ak['hallucination_resistance']:.1%}"
                  f"  (CA {ak['correct_answers']} / CR {ak['correct_refusals']}"
                  f" / H {ak['hallucinations']})")

    print(f"\n  Total runtime : {elapsed/60:.1f} min")
    print(SEP + "\n")


# -----------------------------------------------------------------------------
# 6. MAIN
# -----------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="RAG benchmark runner")
    parser.add_argument("--skip-ingest", action="store_true",
                        help="Reuse existing benchmark_vector_store/")
    parser.add_argument("--questions-file", default=str(QUESTIONS_FILE))
    parser.add_argument("--out", default="",
                        help="Output JSON path (default: benchmark_results_<ts>.json)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Run only first N questions (0 = all)")
    parser.add_argument("--difficulty", default="",
                        help="Filter to one difficulty tier: factual | reasoning | adversarial")
    parser.add_argument("--from-id", type=int, default=0,
                        help="Run only questions with id >= this value (0 = all)")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Seconds to sleep between RAG call and judge call (default 1.5)")
    args = parser.parse_args()

    # API key
    api_key = os.getenv("GROQ_API_KEY") or settings.GROQ_API_KEY
    if not api_key:
        sys.exit("ERROR: GROQ_API_KEY not set. Add it to .env or set the env var.")

    rag_model = os.getenv("GROQ_MODEL") or settings.GROQ_MODEL or "llama-3.1-8b-instant"
    print(f"RAG model  : {rag_model}")
    print(f"Judge model: {JUDGE_MODEL}")

    # Load questions
    with open(args.questions_file, encoding="utf-8") as f:
        questions: list[dict] = json.load(f)
    if args.limit:
        questions = questions[: args.limit]
    if args.difficulty:
        questions = [q for q in questions if q["difficulty"] == args.difficulty]
    if args.from_id:
        questions = [q for q in questions if q["id"] >= args.from_id]
    print(f"Questions  : {len(questions)}")
    delay = args.delay

    # Ingest
    if args.skip_ingest:
        print("\nLoading existing benchmark_vector_store/ ...")
        vs = VectorStore()
        if not vs.metadata:
            sys.exit("ERROR: benchmark_vector_store/ is empty. Remove --skip-ingest to rebuild.")
    else:
        vs = ingest_benchmark_docs()

    # Build pipeline
    print("\nBuilding pipeline (retriever + reranker) ...", flush=True)
    retriever = HybridRetriever(vs)
    reranker  = Reranker()
    print(f"  BM25 corpus : {len(retriever.documents):,} docs")

    # Run benchmark
    print(f"\n-- Running {len(questions)} questions " + "-" * 35)
    results: list[dict] = []
    t0 = time.time()

    for i, q in enumerate(questions, 1):
        qid  = q["id"]
        diff = q["difficulty"]
        src  = q["source"]
        text = q["question"]

        print(f"  [{i:3d}/{len(questions)}] id={qid} {diff:<12} {src}",
              end=" ... ", flush=True)

        rag_out   = run_rag(text, retriever, reranker, api_key, rag_model)
        time.sleep(delay)

        judge_out = JUDGE_FN[diff](text, rag_out["context"], rag_out["answer"], api_key)
        time.sleep(delay)

        print(f"{judge_out['verdict']}  ({judge_out['score']:.2f})", flush=True)

        results.append({
            "id": qid, "source": src, "difficulty": diff, "question": text,
            "answer": rag_out["answer"],
            "context_sources": rag_out["sources"],
            "judge": judge_out,
        })

    elapsed = time.time() - t0

    # Aggregate & report
    summary = _compute_summary(results)
    _print_report(summary, elapsed)

    # Save
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = args.out or f"benchmark_results_{ts}.json"
    payload = {
        "metadata": {
            "run_at": datetime.now().isoformat(),
            "questions": len(questions),
            "rag_model": rag_model,
            "judge_model": JUDGE_MODEL,
            "vector_store": BENCHMARK_VS,
        },
        "summary": summary,
        "individual_results": results,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Results saved -> {out_path}\n")


if __name__ == "__main__":
    main()