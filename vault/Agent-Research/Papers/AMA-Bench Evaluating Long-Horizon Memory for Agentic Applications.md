---
title: AMA-Bench: Evaluating Long-Horizon Memory for Agentic Applications
authors: [Yujie Zhao, Boqin Yuan, Junbo Huang, Haocheng Yuan, Zhongming Yu]
arxiv_id: 2602.22769v1
published: 2026-02-26T08:59:31+00:00
pdf_url: https://arxiv.org/pdf/2602.22769v1
categories: [cs.AI, cs.LG]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# AMA-Bench: Evaluating Long-Horizon Memory for Agentic Applications

**Authors:** Yujie Zhao, Boqin Yuan, Junbo Huang, Haocheng Yuan, Zhongming Yu…
**Published:** 2026-02-26T08:59:31+00:00
**PDF:** [Link](https://arxiv.org/pdf/2602.22769v1)
**Categories:** cs.AI, cs.LG

## Abstract

Large Language Models (LLMs) are deployed as autonomous agents in increasingly complex applications, where enabling long-horizon memory is critical for achieving strong performance. However, a significant gap exists between practical applications and current evaluation standards for agent memory: existing benchmarks primarily focus on dialogue-centric, human-agent interactions. In reality, agent memory consists of a continuous stream of agent-environment interactions that are primarily composed of machine-generated representations. To bridge this gap, we introduce AMA-Bench (Agent Memory with Any length), which evaluates long-horizon memory for LLMs in real agentic applications. It features two key components: (1) a set of real-world agentic trajectories across representative agentic applications, paired with expert-curated QA, and (2) a set of synthetic agentic trajectories that scale to arbitrary horizons, paired with rule-based QA. Our comprehensive study shows that existing memory systems underperform on AMA-Bench primarily because they lack causality and objective information and are constrained by the lossy nature of similarity-based retrieval employed by many memory systems. To address these limitations, we propose AMA-Agent, an effective memory system featuring a causality graph and tool-augmented retrieval. Our results demonstrate that AMA-Agent achieves 57.22% average accuracy on AMA-Bench, surpassing the strongest memory system baselines by 11.16%.

## Key Ideas

> _Pending LLM analysis_

## Notes

