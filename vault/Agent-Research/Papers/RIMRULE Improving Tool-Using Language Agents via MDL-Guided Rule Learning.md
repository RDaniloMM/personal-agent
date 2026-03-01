---
title: RIMRULE: Improving Tool-Using Language Agents via MDL-Guided Rule Learning
authors: [Xiang Gao, Yuguang Yao, Qi Zhang, Kaiwen Dong, Avinash Baidya]
arxiv_id: 2601.00086v2
published: 2025-12-31T19:40:10+00:00
pdf_url: https://arxiv.org/pdf/2601.00086v2
categories: [cs.CL]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# RIMRULE: Improving Tool-Using Language Agents via MDL-Guided Rule Learning

**Authors:** Xiang Gao, Yuguang Yao, Qi Zhang, Kaiwen Dong, Avinash Baidya…
**Published:** 2025-12-31T19:40:10+00:00
**PDF:** [Link](https://arxiv.org/pdf/2601.00086v2)
**Categories:** cs.CL

## Abstract

Large language models (LLMs) often struggle to use tools reliably in domain-specific settings, where APIs may be idiosyncratic, under-documented, or tailored to private workflows. This highlights the need for effective adaptation to task-specific tools. We propose RIMRULE, a neuro-symbolic approach for LLM adaptation based on dynamic rule injection. Compact, interpretable rules are distilled from failure traces and injected into the prompt during inference to improve task performance. These rules are proposed by the LLM itself and consolidated using a Minimum Description Length (MDL) objective that favors generality and conciseness. Each rule is stored in both natural language and a structured symbolic form, supporting efficient retrieval at inference time. Experiments on tool-use benchmarks show that this approach improves accuracy on both seen and unseen tools without modifying LLM weights. It outperforms prompting-based adaptation methods and complements finetuning. Moreover, rules learned from one LLM can be reused to improve others, including long reasoning LLMs, highlighting the portability of symbolic knowledge across architectures.

## Key Ideas

> _Pending LLM analysis_

## Notes

