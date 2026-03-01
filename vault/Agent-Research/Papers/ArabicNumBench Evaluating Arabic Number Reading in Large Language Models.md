---
title: ArabicNumBench: Evaluating Arabic Number Reading in Large Language Models
authors: [Anas Alhumud, Abdulaziz Alhammadi, Muhammad Badruddin Khan]
arxiv_id: 2602.18776v1
published: 2026-02-21T10:00:56+00:00
pdf_url: https://arxiv.org/pdf/2602.18776v1
categories: [cs.CL, cs.AI]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# ArabicNumBench: Evaluating Arabic Number Reading in Large Language Models

**Authors:** Anas Alhumud, Abdulaziz Alhammadi, Muhammad Badruddin Khan
**Published:** 2026-02-21T10:00:56+00:00
**PDF:** [Link](https://arxiv.org/pdf/2602.18776v1)
**Categories:** cs.CL, cs.AI

## Abstract

We present ArabicNumBench, a comprehensive benchmark for evaluating large language models on Arabic number reading tasks across Eastern Arabic-Indic numerals (0-9 in Arabic script) and Western Arabic numerals (0-9). We evaluate 71 models from 10 providers using four prompting strategies (zero-shot, zero-shot CoT, few-shot, few-shot CoT) on 210 number reading tasks spanning six contextual categories: pure numerals, addresses, dates, quantities, and prices. Our evaluation comprises 59,010 individual test cases and tracks extraction methods to measure structured output generation. Evaluation reveals substantial performance variation, with accuracy ranging from 14.29\% to 99.05\% across models and strategies. Few-shot Chain-of-Thought prompting achieves 2.8x higher accuracy than zero-shot approaches (80.06\% vs 28.76\%). A striking finding emerges: models achieving elite accuracy (98-99\%) often produce predominantly unstructured output, with most responses lacking Arabic CoT markers. Only 6 models consistently generate structured output across all test cases, while the majority require fallback extraction methods despite high numerical accuracy. Comprehensive evaluation of 281 model-strategy combinations demonstrates that numerical accuracy and instruction-following represent distinct capabilities, establishing baselines for Arabic number comprehension and providing actionable guidance for model selection in production Arabic NLP systems.

## Key Ideas

> _Pending LLM analysis_

## Notes

