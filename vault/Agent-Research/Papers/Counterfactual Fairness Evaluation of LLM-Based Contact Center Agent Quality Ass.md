---
title: Counterfactual Fairness Evaluation of LLM-Based Contact Center Agent Quality Assurance System
authors: [Kawin Mayilvaghanan, Siddhant Gupta, Ayush Kumar]
arxiv_id: 2602.14970v1
published: 2026-02-16T17:56:18+00:00
pdf_url: https://arxiv.org/pdf/2602.14970v1
categories: [cs.CL]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# Counterfactual Fairness Evaluation of LLM-Based Contact Center Agent Quality Assurance System

**Authors:** Kawin Mayilvaghanan, Siddhant Gupta, Ayush Kumar
**Published:** 2026-02-16T17:56:18+00:00
**PDF:** [Link](https://arxiv.org/pdf/2602.14970v1)
**Categories:** cs.CL

## Abstract

Large Language Models (LLMs) are increasingly deployed in contact-center Quality Assurance (QA) to automate agent performance evaluation and coaching feedback. While LLMs offer unprecedented scalability and speed, their reliance on web-scale training data raises concerns regarding demographic and behavioral biases that may distort workforce assessment. We present a counterfactual fairness evaluation of LLM-based QA systems across 13 dimensions spanning three categories: Identity, Context, and Behavioral Style. Fairness is quantified using the Counterfactual Flip Rate (CFR), the frequency of binary judgment reversals, and the Mean Absolute Score Difference (MASD), the average shift in coaching or confidence scores across counterfactual pairs. Evaluating 18 LLMs on 3,000 real-world contact center transcripts, we find systematic disparities, with CFR ranging from 5.4% to 13.0% and consistent MASD shifts across confidence, positive, and improvement scores. Larger, more strongly aligned models show lower unfairness, though fairness does not track accuracy. Contextual priming of historical performance induces the most severe degradations (CFR up to 16.4%), while implicit linguistic identity cues remain a persistent bias source. Finally, we analyze the efficacy of fairness-aware prompting, finding that explicit instructions yield only modest improvements in evaluative consistency. Our findings underscore the need for standardized fairness auditing pipelines prior to deploying LLMs in high-stakes workforce evaluation.

## Key Ideas

> _Pending LLM analysis_

## Notes

