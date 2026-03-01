---
title: Evaluating Stochasticity in Deep Research Agents
authors: [Haotian Zhai, Elias Stengel-Eskin, Pratik Patil, Liu Leqi]
arxiv_id: 2602.23271v1
published: 2026-02-26T17:46:42+00:00
pdf_url: https://arxiv.org/pdf/2602.23271v1
categories: [cs.AI]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# Evaluating Stochasticity in Deep Research Agents

**Authors:** Haotian Zhai, Elias Stengel-Eskin, Pratik Patil, Liu Leqi
**Published:** 2026-02-26T17:46:42+00:00
**PDF:** [Link](https://arxiv.org/pdf/2602.23271v1)
**Categories:** cs.AI

## Abstract

Deep Research Agents (DRAs) are promising agentic systems that gather and synthesize information to support research across domains such as financial decision-making, medical analysis, and scientific discovery. Despite recent improvements in research quality (e.g., outcome accuracy when ground truth is available), DRA system design often overlooks a critical barrier to real-world deployment: stochasticity. Under identical queries, repeated executions of DRAs can exhibit substantial variability in terms of research outcome, findings, and citations. In this paper, we formalize the study of stochasticity in DRAs by modeling them as information acquisition Markov Decision Processes. We introduce an evaluation framework that quantifies variance in the system and identify three sources of it: information acquisition, information compression, and inference. Through controlled experiments, we investigate how stochasticity from these modules across different decision steps influences the variance of DRA outputs. Our results show that reducing stochasticity can improve research output quality, with inference and early-stage stochasticity contributing the most to DRA output variance. Based on these findings, we propose strategies for mitigating stochasticity while maintaining output quality via structured output and ensemble-based query generation. Our experiments on DeepSearchQA show that our proposed mitigation methods reduce average stochasticity by 22% while maintaining high research quality.

## Key Ideas

> _Pending LLM analysis_

## Notes

