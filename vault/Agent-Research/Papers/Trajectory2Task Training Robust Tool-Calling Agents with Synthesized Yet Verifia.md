---
title: Trajectory2Task: Training Robust Tool-Calling Agents with Synthesized Yet Verifiable Data for Complex User Intents
authors: [Ziyi Wang, Yuxuan Lu, Yimeng Zhang, Ziwei Dong, Jing Huang]
arxiv_id: 2601.20144v2
published: 2026-01-28T00:36:13+00:00
pdf_url: https://arxiv.org/pdf/2601.20144v2
categories: [cs.CL]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# Trajectory2Task: Training Robust Tool-Calling Agents with Synthesized Yet Verifiable Data for Complex User Intents

**Authors:** Ziyi Wang, Yuxuan Lu, Yimeng Zhang, Ziwei Dong, Jing Huang…
**Published:** 2026-01-28T00:36:13+00:00
**PDF:** [Link](https://arxiv.org/pdf/2601.20144v2)
**Categories:** cs.CL

## Abstract

Tool-calling agents are increasingly deployed in real-world customer-facing workflows. Yet most studies on tool-calling agents focus on idealized settings with general, fixed, and well-specified tasks. In real-world applications, user requests are often (1) ambiguous, (2) changing over time, or (3) infeasible due to policy constraints, and training and evaluation data that cover these diverse, complex interaction patterns remain under-represented. To bridge the gap, we present Trajectory2Task, a verifiable data generation pipeline for studying tool use at scale under three realistic user scenarios: ambiguous intent, changing intent, and infeasible intents. The pipeline first conducts multi-turn exploration to produce valid tool-call trajectories. It then converts these trajectories into user-facing tasks with controlled intent adaptations. This process yields verifiable task that support closed-loop evaluation and training. We benchmark seven state-of-the-art LLMs on the generated complex user scenario tasks and observe frequent failures. Finally, using successful trajectories obtained from task rollouts, we fine-tune lightweight LLMs and find consistent improvements across all three conditions, along with better generalization to unseen tool-use domains, indicating stronger general tool-calling ability.

## Key Ideas

> _Pending LLM analysis_

## Notes

