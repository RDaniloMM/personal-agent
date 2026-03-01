---
title: Replayable Financial Agents: A Determinism-Faithfulness Assurance Harness for Tool-Using LLM Agents
authors: [Raffi Khatchadourian]
arxiv_id: 2601.15322v1
published: 2026-01-17T19:47:55+00:00
pdf_url: https://arxiv.org/pdf/2601.15322v1
categories: [cs.AI, cs.CL]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# Replayable Financial Agents: A Determinism-Faithfulness Assurance Harness for Tool-Using LLM Agents

**Authors:** Raffi Khatchadourian
**Published:** 2026-01-17T19:47:55+00:00
**PDF:** [Link](https://arxiv.org/pdf/2601.15322v1)
**Categories:** cs.AI, cs.CL

## Abstract

LLM agents struggle with regulatory audit replay: when asked to reproduce a flagged transaction decision with identical inputs, most deployments fail to return consistent results. This paper introduces the Determinism-Faithfulness Assurance Harness (DFAH), a framework for measuring trajectory determinism and evidence-conditioned faithfulness in tool-using agents deployed in financial services.
  Across 74 configurations (12 models, 4 providers, 8-24 runs each at T=0.0) in non-agentic baseline experiments, 7-20B parameter models achieved 100% determinism, while 120B+ models required 3.7x larger validation samples to achieve equivalent statistical reliability. Agentic tool-use introduces additional variance (see Tables 4-7). Contrary to the assumed reliability-capability trade-off, a positive Pearson correlation emerged (r = 0.45, p < 0.01, n = 51 at T=0.0) between determinism and faithfulness; models producing consistent outputs also tended to be more evidence-aligned.
  Three financial benchmarks are provided (compliance triage, portfolio constraints, DataOps exceptions; 50 cases each) along with an open-source stress-test harness. In these benchmarks and under DFAH evaluation settings, Tier 1 models with schema-first architectures achieved determinism levels consistent with audit replay requirements.

## Key Ideas

> _Pending LLM analysis_

## Notes

