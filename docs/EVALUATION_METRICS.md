# RAG Evaluation and Benchmarking Framework

This document details the evaluation framework (`backend/evaluation/`) used to measure retrieval accuracy, citation precision, and hallucination rates.

## 1. Evaluation Dimensions

To validate the reliability of legal answers, evaluation is divided into two distinct tiers:

### 1. Retrieval Quality Metrics
- **Mean Reciprocal Rank (MRR@K)**: Measures where the first relevant legal clause appears in the ranked list.
- **Hit Rate / Recall@K**: Proportion of queries where the ground-truth document chunk is within the top $K$ retrieved chunks.
- **Normalized Discounted Cumulative Gain (NDCG@K)**: Evaluates ranking sensitivity to relevance grade.

### 2. Generation Quality Metrics
- **Faithfulness / Groundedness**: The proportion of generated claims directly entailing facts present in the cited chunks.
- **Answer Relevance**: Semantic similarity between the user inquiry and generated answer.
- **Citation Precision**: The percentage of citations in the generated response that actually support the preceding claim.

---

## 2. Evaluation Dataset Structure

Test samples are structured in `backend/evaluation/test_cases.json`:
```json
[
  {
    "id": "eval_001",
    "query": "Is there a mortgage registered with State Bank of India?",
    "expected_document": "encumbrance_cert_2025.pdf",
    "expected_status": "supported",
    "ground_truth_chunks": ["chunk_uuid_88"],
    "ground_truth_answer": "No mortgage registered with State Bank of India."
  }
]
```

---

## 3. Running Automated Evaluation

```bash
cd backend
python -m evaluation.run_benchmarks --top-k 5 --dataset evaluation/test_cases.json
```
Reports are output in JSON and Markdown formats displaying aggregate scores.
