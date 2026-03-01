---
title: A Framework for Assessing AI Agent Decisions and Outcomes in AutoML Pipelines
authors: [Gaoyuan Du, Amit Ahlawat, Xiaoyang Liu, Jing Wu]
arxiv_id: 2602.22442v1
published: 2026-02-25T22:02:00+00:00
pdf_url: https://arxiv.org/pdf/2602.22442v1
categories: [cs.AI]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# A Framework for Assessing AI Agent Decisions and Outcomes in AutoML Pipelines

**Authors:** Gaoyuan Du, Amit Ahlawat, Xiaoyang Liu, Jing Wu
**Published:** 2026-02-25T22:02:00+00:00
**PDF:** [Link](https://arxiv.org/pdf/2602.22442v1)
**Categories:** cs.AI

## Abstract

Agent-based AutoML systems rely on large language models to make complex, multi-stage decisions across data processing, model selection, and evaluation. However, existing evaluation practices remain outcome-centric, focusing primarily on final task performance. Through a review of prior work, we find that none of the surveyed agentic AutoML systems report structured, decision-level evaluation metrics intended for post-hoc assessment of intermediate decision quality. To address this limitation, we propose an Evaluation Agent (EA) that performs decision-centric assessment of AutoML agents without interfering with their execution. The EA is designed as an observer that evaluates intermediate decisions along four dimensions: decision validity, reasoning consistency, model quality risks beyond accuracy, and counterfactual decision impact. Across four proof-of-concept experiments, we demonstrate that the EA can (i) detect faulty decisions with an F1 score of 0.919, (ii) identify reasoning inconsistencies independent of final outcomes, and (iii) attribute downstream performance changes to agent decisions, revealing impacts ranging from -4.9\% to +8.3\% in final metrics. These results illustrate how decision-centric evaluation exposes failure modes that are invisible to outcome-only metrics. Our work reframes the evaluation of agentic AutoML systems from an outcome-based perspective to one that audits agent decisions, offering a foundation for reliable, interpretable, and governable autonomous ML systems.

## Key Ideas

> _Pending LLM analysis_

## Notes

