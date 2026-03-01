---
title: Spatio-Temporal Token Pruning for Efficient High-Resolution GUI Agents
authors: [Zhou Xu, Bowen Zhou, Qi Wang, Shuwen Feng, Jingyu Xiao]
arxiv_id: 2602.23235v1
published: 2026-02-26T17:12:40+00:00
pdf_url: https://arxiv.org/pdf/2602.23235v1
categories: [cs.CV, cs.AI]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# Spatio-Temporal Token Pruning for Efficient High-Resolution GUI Agents

**Authors:** Zhou Xu, Bowen Zhou, Qi Wang, Shuwen Feng, Jingyu Xiao
**Published:** 2026-02-26T17:12:40+00:00
**PDF:** [Link](https://arxiv.org/pdf/2602.23235v1)
**Categories:** cs.CV, cs.AI

## Abstract

Pure-vision GUI agents provide universal interaction capabilities but suffer from severe efficiency bottlenecks due to the massive spatiotemporal redundancy inherent in high-resolution screenshots and historical trajectories. We identify two critical misalignments in existing compression paradigms: the temporal mismatch, where uniform history encoding diverges from the agent's "fading memory" attention pattern, and the spatial topology conflict, where unstructured pruning compromises the grid integrity required for precise coordinate grounding, inducing spatial hallucinations. To address these challenges, we introduce GUIPruner, a training-free framework tailored for high-resolution GUI navigation. It synergizes Temporal-Adaptive Resolution (TAR), which eliminates historical redundancy via decay-based resizing, and Stratified Structure-aware Pruning (SSP), which prioritizes interactive foregrounds and semantic anchors while safeguarding global layout. Extensive evaluations across diverse benchmarks demonstrate that GUIPruner consistently achieves state-of-the-art performance, effectively preventing the collapse observed in large-scale models under high compression. Notably, on Qwen2-VL-2B, our method delivers a 3.4x reduction in FLOPs and a 3.3x speedup in vision encoding latency while retaining over 94% of the original performance, enabling real-time, high-precision navigation with minimal resource consumption.

## Key Ideas

> _Pending LLM analysis_

## Notes

