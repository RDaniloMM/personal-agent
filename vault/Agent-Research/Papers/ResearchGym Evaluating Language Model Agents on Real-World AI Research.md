---
title: ResearchGym: Evaluating Language Model Agents on Real-World AI Research
authors: [Aniketh Garikaparthi, Manasi Patwardhan, Arman Cohan]
arxiv_id: 2602.15112v1
published: 2026-02-16T19:00:03+00:00
pdf_url: https://arxiv.org/pdf/2602.15112v1
categories: [cs.AI]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# ResearchGym: Evaluating Language Model Agents on Real-World AI Research

**Authors:** Aniketh Garikaparthi, Manasi Patwardhan, Arman Cohan
**Published:** 2026-02-16T19:00:03+00:00
**PDF:** [Link](https://arxiv.org/pdf/2602.15112v1)
**Categories:** cs.AI

## Abstract

We introduce ResearchGym, a benchmark and execution environment for evaluating AI agents on end-to-end research. To instantiate this, we repurpose five oral and spotlight papers from ICML, ICLR, and ACL. From each paper's repository, we preserve the datasets, evaluation harness, and baseline implementations but withhold the paper's proposed method. This results in five containerized task environments comprising 39 sub-tasks in total. Within each environment, agents must propose novel hypotheses, run experiments, and attempt to surpass strong human baselines on the paper's metrics. In a controlled evaluation of an agent powered by GPT-5, we observe a sharp capability--reliability gap. The agent improves over the provided baselines from the repository in just 1 of 15 evaluations (6.7%) by 11.5%, and completes only 26.5% of sub-tasks on average. We identify recurring long-horizon failure modes, including impatience, poor time and resource management, overconfidence in weak hypotheses, difficulty coordinating parallel experiments, and hard limits from context length. Yet in a single run, the agent surpasses the solution of an ICML 2025 Spotlight task, indicating that frontier agents can occasionally reach state-of-the-art performance, but do so unreliably. We additionally evaluate proprietary agent scaffolds including Claude Code (Opus-4.5) and Codex (GPT-5.2) which display a similar gap. ResearchGym provides infrastructure for systematic evaluation and analysis of autonomous agents on closed-loop research.

## Key Ideas

> _Pending LLM analysis_

## Notes

