---
title: CoLT: Reasoning with Chain of Latent Tool Calls
authors: [Fangwei Zhu, Zhifang Sui]
arxiv_id: 2602.04246v1
published: 2026-02-04T06:12:53+00:00
pdf_url: https://arxiv.org/pdf/2602.04246v1
categories: [cs.CL]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# CoLT: Reasoning with Chain of Latent Tool Calls

**Authors:** Fangwei Zhu, Zhifang Sui
**Published:** 2026-02-04T06:12:53+00:00
**PDF:** [Link](https://arxiv.org/pdf/2602.04246v1)
**Categories:** cs.CL

## Abstract

Chain-of-Thought (CoT) is a critical technique in enhancing the reasoning ability of Large Language Models (LLMs), and latent reasoning methods have been proposed to accelerate the inefficient token-level reasoning chain. We notice that existing latent reasoning methods generally require model structure augmentation and exhaustive training, limiting their broader applicability. In this paper, we propose CoLT, a novel framework that implements latent reasoning as ``tool calls''. Instead of reasoning entirely in the latent space, CoLT generates seed tokens that contain information of a reasoning step. When a latent tool call is triggered, a smaller external model will take the hidden states of seed tokens as its input, and unpack the seed tokens back to a full reasoning step. In this way, we can ensure that the main model reasons in the explicit token space, preserving its ability while improving efficiency. Experimental results on four mathematical datasets demonstrate that CoLT achieves higher accuracy and shorter reasoning length than baseline latent models, and is compatible with reinforcement learning algorithms and different decoder structures.

## Key Ideas

> _Pending LLM analysis_

## Notes

