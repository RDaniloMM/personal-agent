---
title: The Confidence Dichotomy: Analyzing and Mitigating Miscalibration in Tool-Use Agents
authors: [Weihao Xuan, Qingcheng Zeng, Heli Qi, Yunze Xiao, Junjue Wang]
arxiv_id: 2601.07264v1
published: 2026-01-12T07:10:35+00:00
pdf_url: https://arxiv.org/pdf/2601.07264v1
categories: [cs.CL]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# The Confidence Dichotomy: Analyzing and Mitigating Miscalibration in Tool-Use Agents

**Authors:** Weihao Xuan, Qingcheng Zeng, Heli Qi, Yunze Xiao, Junjue Wang…
**Published:** 2026-01-12T07:10:35+00:00
**PDF:** [Link](https://arxiv.org/pdf/2601.07264v1)
**Categories:** cs.CL

## Abstract

Autonomous agents based on large language models (LLMs) are rapidly evolving to handle multi-turn tasks, but ensuring their trustworthiness remains a critical challenge. A fundamental pillar of this trustworthiness is calibration, which refers to an agent's ability to express confidence that reliably reflects its actual performance. While calibration is well-established for static models, its dynamics in tool-integrated agentic workflows remain underexplored. In this work, we systematically investigate verbalized calibration in tool-use agents, revealing a fundamental confidence dichotomy driven by tool type. Specifically, our pilot study identifies that evidence tools (e.g., web search) systematically induce severe overconfidence due to inherent noise in retrieved information, while verification tools (e.g., code interpreters) can ground reasoning through deterministic feedback and mitigate miscalibration. To robustly improve calibration across tool types, we propose a reinforcement learning (RL) fine-tuning framework that jointly optimizes task accuracy and calibration, supported by a holistic benchmark of reward designs. We demonstrate that our trained agents not only achieve superior calibration but also exhibit robust generalization from local training environments to noisy web settings and to distinct domains such as mathematical reasoning. Our results highlight the necessity of domain-specific calibration strategies for tool-use agents. More broadly, this work establishes a foundation for building self-aware agents that can reliably communicate uncertainty in high-stakes, real-world deployments.

## Key Ideas

> _Pending LLM analysis_

## Notes

