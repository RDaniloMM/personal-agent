---
title: Luna-2: Scalable Single-Token Evaluation with Small Language Models
authors: [Vatsal Goel, Rishon Dsouza, Nikhil Ega, Amey Ramesh Rambatla, Rob Friel]
arxiv_id: 2602.18583v1
published: 2026-02-20T19:43:58+00:00
pdf_url: https://arxiv.org/pdf/2602.18583v1
categories: [cs.CL, cs.AI, cs.LG]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# Luna-2: Scalable Single-Token Evaluation with Small Language Models

**Authors:** Vatsal Goel, Rishon Dsouza, Nikhil Ega, Amey Ramesh Rambatla, Rob Friel…
**Published:** 2026-02-20T19:43:58+00:00
**PDF:** [Link](https://arxiv.org/pdf/2602.18583v1)
**Categories:** cs.CL, cs.AI, cs.LG

## Abstract

Real-time guardrails require evaluation that is accurate, cheap, and fast - yet today's default, LLM-as-a-judge (LLMAJ), is slow, expensive, and operationally non-deterministic due to multi-token generation. We present Luna-2, a novel architecture that leverages decoder-only small language models (SLMs) into a deterministic evaluation model to reliably compute complex task-specific LLMAJ metrics (e.g. toxicity, hallucination, tool selection quality, etc.) at an accuracy at par or higher than LLMAJ using frontier LLMs while drastically reducing the cost and latency of computation. Each metric is implemented as a lightweight LoRA/PEFT head on top of a shared SLM backbone, enabling hundreds of specialized metrics to run concurrently on a single GPU, deployable locally next to AI systems in a privacy-preserving and latency optimizing manner. Across content safety and hallucination benchmarks, Luna-2 matches the accuracy of state-of-the-art LLM-based evaluators while reducing inference cost by over 80x and latency by over 20x.
  In this paper, we outline the model architecture, training methodology and report real-world empirical results on accuracy, latency, and throughput results. In production, Luna-2 is protecting 100M+ AI sessions and processing over 100B tokens per month for our customers with eval cost savings of over $30M annually.

## Key Ideas

> _Pending LLM analysis_

## Notes

