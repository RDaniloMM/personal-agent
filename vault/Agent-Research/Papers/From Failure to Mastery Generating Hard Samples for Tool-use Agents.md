---
title: From Failure to Mastery: Generating Hard Samples for Tool-use Agents
authors: [Bingguang Hao, Zengzhuang Xu, Yuntao Wen, Xinyi Xu, Yang Liu]
arxiv_id: 2601.01498v1
published: 2026-01-04T11:56:33+00:00
pdf_url: https://arxiv.org/pdf/2601.01498v1
categories: [cs.CL]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# From Failure to Mastery: Generating Hard Samples for Tool-use Agents

**Authors:** Bingguang Hao, Zengzhuang Xu, Yuntao Wen, Xinyi Xu, Yang Liu…
**Published:** 2026-01-04T11:56:33+00:00
**PDF:** [Link](https://arxiv.org/pdf/2601.01498v1)
**Categories:** cs.CL

## Abstract

The advancement of LLM agents with tool-use capabilities requires diverse and complex training corpora. Existing data generation methods, which predominantly follow a paradigm of random sampling and shallow generation, often yield simple and homogeneous trajectories that fail to capture complex, implicit logical dependencies. To bridge this gap, we introduce HardGen, an automatic agentic pipeline designed to generate hard tool-use training samples with verifiable reasoning. Firstly, HardGen establishes a dynamic API Graph built upon agent failure cases, from which it samples to synthesize hard traces. Secondly, these traces serve as conditional priors to guide the instantiation of modular, abstract advanced tools, which are subsequently leveraged to formulate hard queries. Finally, the advanced tools and hard queries enable the generation of verifiable complex Chain-of-Thought (CoT), with a closed-loop evaluation feedback steering the continuous refinement of the process. Extensive evaluations demonstrate that a 4B parameter model trained with our curated dataset achieves superior performance compared to several leading open-source and closed-source competitors (e.g., GPT-5.2, Gemini-3-Pro and Claude-Opus-4.5). Our code, models, and dataset will be open-sourced to facilitate future research.

## Key Ideas

> _Pending LLM analysis_

## Notes

