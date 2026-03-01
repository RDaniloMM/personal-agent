---
title: Towards Simulating Social Media Users with LLMs: Evaluating the Operational Validity of Conditioned Comment Prediction
authors: [Nils Schwager, Simon Münker, Alistair Plum, Achim Rettinger]
arxiv_id: 2602.22752v1
published: 2026-02-26T08:40:21+00:00
pdf_url: https://arxiv.org/pdf/2602.22752v1
categories: [cs.CL, cs.AI]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# Towards Simulating Social Media Users with LLMs: Evaluating the Operational Validity of Conditioned Comment Prediction

**Authors:** Nils Schwager, Simon Münker, Alistair Plum, Achim Rettinger
**Published:** 2026-02-26T08:40:21+00:00
**PDF:** [Link](https://arxiv.org/pdf/2602.22752v1)
**Categories:** cs.CL, cs.AI

## Abstract

The transition of Large Language Models (LLMs) from exploratory tools to active "silicon subjects" in social science lacks extensive validation of operational validity. This study introduces Conditioned Comment Prediction (CCP), a task in which a model predicts how a user would comment on a given stimulus by comparing generated outputs with authentic digital traces. This framework enables a rigorous evaluation of current LLM capabilities with respect to the simulation of social media user behavior. We evaluated open-weight 8B models (Llama3.1, Qwen3, Ministral) in English, German, and Luxembourgish language scenarios. By systematically comparing prompting strategies (explicit vs. implicit) and the impact of Supervised Fine-Tuning (SFT), we identify a critical form vs. content decoupling in low-resource settings: while SFT aligns the surface structure of the text output (length and syntax), it degrades semantic grounding. Furthermore, we demonstrate that explicit conditioning (generated biographies) becomes redundant under fine-tuning, as models successfully perform latent inference directly from behavioral histories. Our findings challenge current "naive prompting" paradigms and offer operational guidelines prioritizing authentic behavioral traces over descriptive personas for high-fidelity simulation.

## Key Ideas

> _Pending LLM analysis_

## Notes

