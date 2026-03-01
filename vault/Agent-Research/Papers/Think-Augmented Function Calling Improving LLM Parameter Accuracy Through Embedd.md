---
title: Think-Augmented Function Calling: Improving LLM Parameter Accuracy Through Embedded Reasoning
authors: [Lei Wei, Xiao Peng, Jinpeng Ou, Bin Wang]
arxiv_id: 2601.18282v2
published: 2026-01-26T09:05:00+00:00
pdf_url: https://arxiv.org/pdf/2601.18282v2
categories: [cs.AI, cs.CL, cs.LG]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# Think-Augmented Function Calling: Improving LLM Parameter Accuracy Through Embedded Reasoning

**Authors:** Lei Wei, Xiao Peng, Jinpeng Ou, Bin Wang
**Published:** 2026-01-26T09:05:00+00:00
**PDF:** [Link](https://arxiv.org/pdf/2601.18282v2)
**Categories:** cs.AI, cs.CL, cs.LG

## Abstract

Large language models (LLMs) have demonstrated remarkable capabilities in function calling for autonomous agents, yet current mechanisms lack explicit reasoning transparency during parameter generation, particularly for complex functions with interdependent parameters. While existing approaches like chain-of-thought prompting operate at the agent level, they fail to provide fine-grained reasoning guidance for individual function parameters. To address these limitations, we propose Think-Augmented Function Calling (TAFC), a novel framework that enhances function calling accuracy through explicit reasoning at both function and parameter levels. Our method introduces a universal "think" parameter augmentation that enables models to articulate their decision-making process, with dynamic optimization for parameter descriptions to improve reasoning quality. For complex parameters, TAFC automatically triggers granular reasoning based on complexity scoring, ensuring appropriate justification for critical decisions. Additionally, we propose reasoning-guided optimization to align generated reasoning with human expectations. TAFC requires no architectural modifications to existing LLMs while maintaining full API compatibility. Evaluation on ToolBench across proprietary and open-source models demonstrates significant improvements in parameter generation accuracy and reasoning coherence for multi-parameter functions, while providing enhanced interpretability for debugging AI agent behaviors.

## Key Ideas

> _Pending LLM analysis_

## Notes

