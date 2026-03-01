---
title: Unsafer in Many Turns: Benchmarking and Defending Multi-Turn Safety Risks in Tool-Using Agents
authors: [Xu Li, Simon Yu, Minzhou Pan, Yiyou Sun, Bo Li]
arxiv_id: 2602.13379v1
published: 2026-02-13T18:38:18+00:00
pdf_url: https://arxiv.org/pdf/2602.13379v1
categories: [cs.CR, cs.AI, cs.CL, cs.LG, cs.SE]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# Unsafer in Many Turns: Benchmarking and Defending Multi-Turn Safety Risks in Tool-Using Agents

**Authors:** Xu Li, Simon Yu, Minzhou Pan, Yiyou Sun, Bo Li…
**Published:** 2026-02-13T18:38:18+00:00
**PDF:** [Link](https://arxiv.org/pdf/2602.13379v1)
**Categories:** cs.CR, cs.AI, cs.CL, cs.LG, cs.SE

## Abstract

LLM-based agents are becoming increasingly capable, yet their safety lags behind. This creates a gap between what agents can do and should do. This gap widens as agents engage in multi-turn interactions and employ diverse tools, introducing new risks overlooked by existing benchmarks. To systematically scale safety testing into multi-turn, tool-realistic settings, we propose a principled taxonomy that transforms single-turn harmful tasks into multi-turn attack sequences. Using this taxonomy, we construct MT-AgentRisk (Multi-Turn Agent Risk Benchmark), the first benchmark to evaluate multi-turn tool-using agent safety. Our experiments reveal substantial safety degradation: the Attack Success Rate (ASR) increases by 16% on average across open and closed models in multi-turn settings. To close this gap, we propose ToolShield, a training-free, tool-agnostic, self-exploration defense: when encountering a new tool, the agent autonomously generates test cases, executes them to observe downstream effects, and distills safety experiences for deployment. Experiments show that ToolShield effectively reduces ASR by 30% on average in multi-turn interactions. Our code is available at https://github.com/CHATS-lab/ToolShield.

## Key Ideas

> _Pending LLM analysis_

## Notes

