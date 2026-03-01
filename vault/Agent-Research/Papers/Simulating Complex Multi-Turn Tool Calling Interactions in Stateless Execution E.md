---
title: Simulating Complex Multi-Turn Tool Calling Interactions in Stateless Execution Environments
authors: [Maxwell Crouse, Ibrahim Abdelaziz, Kshitij Fadnis, Siva Sankalp Patel, Kinjal Basu]
arxiv_id: 2601.19914v1
published: 2026-01-06T20:04:30+00:00
pdf_url: https://arxiv.org/pdf/2601.19914v1
categories: [cs.CL, cs.AI, cs.SE]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# Simulating Complex Multi-Turn Tool Calling Interactions in Stateless Execution Environments

**Authors:** Maxwell Crouse, Ibrahim Abdelaziz, Kshitij Fadnis, Siva Sankalp Patel, Kinjal Basu…
**Published:** 2026-01-06T20:04:30+00:00
**PDF:** [Link](https://arxiv.org/pdf/2601.19914v1)
**Categories:** cs.CL, cs.AI, cs.SE

## Abstract

Synthetic data has proven itself to be a valuable resource for tuning smaller, cost-effective language models to handle the complexities of multi-turn tool calling conversations. While many frameworks and systems for producing synthetic multi-turn tool calling data have been proposed, prior works have frequently assumed that any tool calling interactions will take place in an execution environment that maintains state. When such an environment is available, this is advantageous as it allows for the validity of an interaction to be determined by whether or not the state of the execution environment matches to some prespecified objective. Unfortunately, this does not hold in many real-world tool use settings, e.g., in enterprise settings where data security is of the utmost importance or in cases where tool specifications are synthesized from multiple sources. In this work, we address this gap by introducing a data generation method, DiGiT-TC, that is designed to produce tool calling conversations that have the characteristics of conversations generated through search in a stateful environment. The key to our technique lies in a novel generation pattern that allows our approach to implicitly represent certain tool calls in the user request. We validate our approach on standard tool calling benchmarks and demonstrate that, even in stateful problem settings, our approach results in strong performance gains.

## Key Ideas

> _Pending LLM analysis_

## Notes

