---
title: Case-Aware LLM-as-a-Judge Evaluation for Enterprise-Scale RAG Systems
authors: [Mukul Chhabra, Luigi Medrano, Arush Verma]
arxiv_id: 2602.20379v1
published: 2026-02-23T21:37:06+00:00
pdf_url: https://arxiv.org/pdf/2602.20379v1
categories: [cs.CL, cs.AI]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# Case-Aware LLM-as-a-Judge Evaluation for Enterprise-Scale RAG Systems

**Authors:** Mukul Chhabra, Luigi Medrano, Arush Verma
**Published:** 2026-02-23T21:37:06+00:00
**PDF:** [Link](https://arxiv.org/pdf/2602.20379v1)
**Categories:** cs.CL, cs.AI

## Abstract

Enterprise Retrieval-Augmented Generation (RAG) assistants operate in multi-turn, case-based workflows such as technical support and IT operations, where evaluation must reflect operational constraints, structured identifiers (e.g., error codes, versions), and resolution workflows. Existing RAG evaluation frameworks are primarily designed for benchmark-style or single-turn settings and often fail to capture enterprise-specific failure modes such as case misidentification, workflow misalignment, and partial resolution across turns.
  We present a case-aware LLM-as-a-Judge evaluation framework for enterprise multi-turn RAG systems. The framework evaluates each turn using eight operationally grounded metrics that separate retrieval quality, grounding fidelity, answer utility, precision integrity, and case/workflow alignment. A severity-aware scoring protocol reduces score inflation and improves diagnostic clarity across heterogeneous enterprise cases. The system uses deterministic prompting with strict JSON outputs, enabling scalable batch evaluation, regression testing, and production monitoring.
  Through a comparative study of two instruction-tuned models across short and long workflows, we show that generic proxy metrics provide ambiguous signals, while the proposed framework exposes enterprise-critical tradeoffs that are actionable for system improvement.

## Key Ideas

> _Pending LLM analysis_

## Notes

