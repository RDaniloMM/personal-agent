---
title: User-Oriented Multi-Turn Dialogue Generation with Tool Use at scale
authors: [Jungho Cho, Minbyul Jeong, Sungrae Park]
arxiv_id: 2601.08225v1
published: 2026-01-13T05:14:09+00:00
pdf_url: https://arxiv.org/pdf/2601.08225v1
categories: [cs.CL]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# User-Oriented Multi-Turn Dialogue Generation with Tool Use at scale

**Authors:** Jungho Cho, Minbyul Jeong, Sungrae Park
**Published:** 2026-01-13T05:14:09+00:00
**PDF:** [Link](https://arxiv.org/pdf/2601.08225v1)
**Categories:** cs.CL

## Abstract

The recent paradigm shift toward large reasoning models (LRMs) as autonomous agents has intensified the demand for sophisticated, multi-turn tool-use capabilities. Yet, existing datasets and data-generation approaches are limited by static, predefined toolsets that cannot scale to the complexity of open-ended human-agent collaboration. To address this, we initially developed a framework for automated task-oriented multi-turn dialogue generation at scale, utilizing an LRM-based simulator to dynamically generate high-value, domain-specific tools to solve specified tasks. However, we observe that a purely task-oriented design often results in "solely task-solving" trajectories, where the agent completes the objective with minimal interaction, failing to generate the high turn-count conversations seen in realistic scenarios. To bridge this gap, we shift toward a user-oriented simulation paradigm. By decoupling task generation from a dedicated user simulator that mimics human behavioral rules - such as incremental request-making and turn-by-turn feedback - we facilitate more authentic, extended multi-turn dialogues that reflect the iterative nature of real-world problem solving. Our generation pipeline operates as a versatile, plug-and-play module capable of initiating generation from any state, ensuring high scalability in producing extended tool-use data. Furthermore, by facilitating multiple task completions within a single trajectory, it yields a high-density dataset that reflects the multifaceted demands of real-world human-agent interaction.

## Key Ideas

> _Pending LLM analysis_

## Notes

