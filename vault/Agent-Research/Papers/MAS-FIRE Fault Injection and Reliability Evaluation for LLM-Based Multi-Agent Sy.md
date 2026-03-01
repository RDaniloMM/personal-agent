---
title: MAS-FIRE: Fault Injection and Reliability Evaluation for LLM-Based Multi-Agent Systems
authors: [Jin Jia, Zhiling Deng, Zhuangbin Chen, Yingqi Wang, Zibin Zheng]
arxiv_id: 2602.19843v1
published: 2026-02-23T13:47:43+00:00
pdf_url: https://arxiv.org/pdf/2602.19843v1
categories: [cs.SE, cs.AI]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# MAS-FIRE: Fault Injection and Reliability Evaluation for LLM-Based Multi-Agent Systems

**Authors:** Jin Jia, Zhiling Deng, Zhuangbin Chen, Yingqi Wang, Zibin Zheng
**Published:** 2026-02-23T13:47:43+00:00
**PDF:** [Link](https://arxiv.org/pdf/2602.19843v1)
**Categories:** cs.SE, cs.AI

## Abstract

As LLM-based Multi-Agent Systems (MAS) are increasingly deployed for complex tasks, ensuring their reliability has become a pressing challenge. Since MAS coordinate through unstructured natural language rather than rigid protocols, they are prone to semantic failures (e.g., hallucinations, misinterpreted instructions, and reasoning drift) that propagate silently without raising runtime exceptions. Prevailing evaluation approaches, which measure only end-to-end task success, offer limited insight into how these failures arise or how effectively agents recover from them. To bridge this gap, we propose MAS-FIRE, a systematic framework for fault injection and reliability evaluation of MAS. We define a taxonomy of 15 fault types covering intra-agent cognitive errors and inter-agent coordination failures, and inject them via three non-invasive mechanisms: prompt modification, response rewriting, and message routing manipulation. Applying MAS-FIRE to three representative MAS architectures, we uncover a rich set of fault-tolerant behaviors that we organize into four tiers: mechanism, rule, prompt, and reasoning. This tiered view enables fine-grained diagnosis of where and why systems succeed or fail. Our findings reveal that stronger foundation models do not uniformly improve robustness. We further show that architectural topology plays an equally decisive role, with iterative, closed-loop designs neutralizing over 40% of faults that cause catastrophic collapse in linear workflows. MAS-FIRE provides the process-level observability and actionable guidance needed to systematically improve multi-agent systems.

## Key Ideas

> _Pending LLM analysis_

## Notes

