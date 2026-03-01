---
title: Linguistic and Argument Diversity in Synthetic Data for Function-Calling Agents
authors: [Dan Greenstein, Zohar Karnin, Chen Amiraz, Oren Somekh]
arxiv_id: 2601.17829v1
published: 2026-01-25T13:20:33+00:00
pdf_url: https://arxiv.org/pdf/2601.17829v1
categories: [cs.CL, cs.AI]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# Linguistic and Argument Diversity in Synthetic Data for Function-Calling Agents

**Authors:** Dan Greenstein, Zohar Karnin, Chen Amiraz, Oren Somekh
**Published:** 2026-01-25T13:20:33+00:00
**PDF:** [Link](https://arxiv.org/pdf/2601.17829v1)
**Categories:** cs.CL, cs.AI

## Abstract

The construction of function calling agents has emerged as a promising avenue for extending model capabilities. A major challenge for this task is obtaining high quality diverse data for training. Prior work emphasizes diversity in functions, invocation patterns, and interaction turns, yet linguistic diversity of requests and coverage of arguments (e.g., \texttt{city\_name}, \texttt{stock\_ticker}) remain underexplored. We propose a method that generates synthetic datasets via optimizing general-purpose diversity metrics across both queries and arguments, without relying on hand-crafted rules or taxonomies, making it robust to different usecases. We demonstrate the effectiveness of our technique via both intrinsic and extrinsic testing, comparing it to SoTA data generation methods. We show a superiority over baselines in terms of diversity, while keeping comparable correctness. Additionally, when used as a training set, the model resulting from our dataset exhibits superior performance compared to analogous models based on the baseline data generation methods in out-of-distribution performance. In particular, we achieve an $7.4\%$ increase in accuracy on the BFCL benchmark compared to similar counterparts.

## Key Ideas

> _Pending LLM analysis_

## Notes

