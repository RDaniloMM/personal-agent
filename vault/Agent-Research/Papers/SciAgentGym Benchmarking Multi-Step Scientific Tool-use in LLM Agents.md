---
title: SciAgentGym: Benchmarking Multi-Step Scientific Tool-use in LLM Agents
authors: [Yujiong Shen, Yajie Yang, Zhiheng Xi, Binze Hu, Huayu Sha]
arxiv_id: 2602.12984v1
published: 2026-02-13T14:58:18+00:00
pdf_url: https://arxiv.org/pdf/2602.12984v1
categories: [cs.CL]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# SciAgentGym: Benchmarking Multi-Step Scientific Tool-use in LLM Agents

**Authors:** Yujiong Shen, Yajie Yang, Zhiheng Xi, Binze Hu, Huayu Sha…
**Published:** 2026-02-13T14:58:18+00:00
**PDF:** [Link](https://arxiv.org/pdf/2602.12984v1)
**Categories:** cs.CL

## Abstract

Scientific reasoning inherently demands integrating sophisticated toolkits to navigate domain-specific knowledge. Yet, current benchmarks largely overlook agents' ability to orchestrate tools for such rigorous workflows. To bridge this gap, we introduce SciAgentGym, a scalable interactive environment featuring 1,780 domain-specific tools across four natural science disciplines, supported by a robust execution infrastructure. Complementing this, we present SciAgentBench, a tiered evaluation suite designed to stress-test agentic capabilities from elementary actions to long-horizon workflows. Our evaluation identifies a critical bottleneck: state-of-the-art models struggle with complex scientific tool-use. Even for a leading model like GPT-5, success rates drop sharply from 60.6% to 30.9% as interaction horizons extend, primarily due to failures in multi-step workflow execution. To address this, we propose SciForge, a data synthesis method that models the tool action space as a dependency graph to generate logic-aware training trajectories. By fine-tuning on these trajectories, our SciAgent-8B outperforms the significantly larger Qwen3-VL-235B-Instruct while exhibiting positive cross-domain transfer of scientific tool-use capabilities. These results underscore the promising potential of next-generation autonomous scientific agents.

## Key Ideas

> _Pending LLM analysis_

## Notes

