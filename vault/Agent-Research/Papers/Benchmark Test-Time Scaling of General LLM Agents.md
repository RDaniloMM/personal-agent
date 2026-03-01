---
title: Benchmark Test-Time Scaling of General LLM Agents
authors: [Xiaochuan Li, Ryan Ming, Pranav Setlur, Abhijay Paladugu, Andy Tang]
arxiv_id: 2602.18998v1
published: 2026-02-22T01:08:02+00:00
pdf_url: https://arxiv.org/pdf/2602.18998v1
categories: [cs.AI, cs.CL]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# Benchmark Test-Time Scaling of General LLM Agents

**Authors:** Xiaochuan Li, Ryan Ming, Pranav Setlur, Abhijay Paladugu, Andy Tang…
**Published:** 2026-02-22T01:08:02+00:00
**PDF:** [Link](https://arxiv.org/pdf/2602.18998v1)
**Categories:** cs.AI, cs.CL

## Abstract

LLM agents are increasingly expected to function as general-purpose systems capable of resolving open-ended user requests. While existing benchmarks focus on domain-aware environments for developing specialized agents, evaluating general-purpose agents requires more realistic settings that challenge them to operate across multiple skills and tools within a unified environment. We introduce General AgentBench, a benchmark that provides such a unified framework for evaluating general LLM agents across search, coding, reasoning, and tool-use domains. Using General AgentBench, we systematically study test-time scaling behaviors under sequential scaling (iterative interaction) and parallel scaling (sampling multiple trajectories). Evaluation of ten leading LLM agents reveals a substantial performance degradation when moving from domain-specific evaluations to this general-agent setting. Moreover, we find that neither scaling methodology yields effective performance improvements in practice, due to two fundamental limitations: context ceiling in sequential scaling and verification gap in parallel scaling. Code is publicly available at https://github.com/cxcscmu/General-AgentBench.

## Key Ideas

> _Pending LLM analysis_

## Notes

