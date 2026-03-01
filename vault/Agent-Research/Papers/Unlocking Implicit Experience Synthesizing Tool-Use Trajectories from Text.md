---
title: Unlocking Implicit Experience: Synthesizing Tool-Use Trajectories from Text
authors: [Zhihao Xu, Rumei Li, Jiahuan Li, Rongxiang Weng, Jingang Wang]
arxiv_id: 2601.10355v1
published: 2026-01-15T12:58:46+00:00
pdf_url: https://arxiv.org/pdf/2601.10355v1
categories: [cs.CL]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# Unlocking Implicit Experience: Synthesizing Tool-Use Trajectories from Text

**Authors:** Zhihao Xu, Rumei Li, Jiahuan Li, Rongxiang Weng, Jingang Wang…
**Published:** 2026-01-15T12:58:46+00:00
**PDF:** [Link](https://arxiv.org/pdf/2601.10355v1)
**Categories:** cs.CL

## Abstract

Enabling Large Language Models (LLMs) to effectively utilize tools in multi-turn interactions is essential for building capable autonomous agents. However, acquiring diverse and realistic multi-turn tool-use data remains a significant challenge. In this work, we propose a novel text-based paradigm. We observe that textual corpora naturally contain rich, multi-step problem-solving experiences, which can serve as an untapped, scalable, and authentic data source for multi-turn tool-use tasks. Based on this insight, we introduce GEM, a data synthesis pipeline that enables the generation and extraction of multi-turn tool-use trajectories from text corpora through a four-stage process: relevance filtering, workflow & tool extraction, trajectory grounding, and complexity refinement. To reduce the computational cost, we further train a specialized Trajectory Synthesizer via supervised fine-tuning. This model distills the complex generation pipeline into an efficient, end-to-end trajectory generator. Experiments demonstrate that our GEM-32B achieve a 16.5% improvement on the BFCL V3 Multi-turn benchmark. Our models partially surpass the performance of models trained on τ - bench (Airline and Retail) in-domain data, highlighting the superior generalization capability derived from our text-based synthesis paradigm. Notably, our Trajectory Synthesizer matches the quality of the full pipeline while significantly reducing inference latency and costs.

## Key Ideas

> _Pending LLM analysis_

## Notes

