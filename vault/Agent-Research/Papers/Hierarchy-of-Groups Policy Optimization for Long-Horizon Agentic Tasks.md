---
title: Hierarchy-of-Groups Policy Optimization for Long-Horizon Agentic Tasks
authors: [Shuo He, Lang Feng, Qi Wei, Xin Cheng, Lei Feng]
arxiv_id: 2602.22817v1
published: 2026-02-26T09:58:10+00:00
pdf_url: https://arxiv.org/pdf/2602.22817v1
categories: [cs.LG, cs.AI]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# Hierarchy-of-Groups Policy Optimization for Long-Horizon Agentic Tasks

**Authors:** Shuo He, Lang Feng, Qi Wei, Xin Cheng, Lei Feng…
**Published:** 2026-02-26T09:58:10+00:00
**PDF:** [Link](https://arxiv.org/pdf/2602.22817v1)
**Categories:** cs.LG, cs.AI

## Abstract

Group-based reinforcement learning (RL), such as GRPO, has advanced the capabilities of large language models on long-horizon agentic tasks. To enable more fine-grained policy updates, recent research has increasingly shifted toward stepwise group-based policy optimization, which treats each step in a rollout trajectory independently while using a memory module to retain historical context. However, we find a key issue in estimating stepwise relative advantages, namely context inconsistency, where steps within the same group may differ in their historical contexts. Empirically, we reveal that this issue can lead to severely biased advantage estimation, thereby degrading policy optimization significantly. To address the issue, in this paper, we propose Hierarchy-of-Groups Policy Optimization (HGPO) for long-horizon agentic tasks. Specifically, within a group of rollout trajectories, HGPO assigns each step to multiple hierarchical groups according to the consistency of historical contexts. Then, for each step, HGPO computes distinct advantages within each group and aggregates them with an adaptive weighting scheme. In this way, HGPO can achieve a favorable bias-variance trade-off in stepwise advantage estimation, without extra models or rollouts. Evaluations on two challenging agentic tasks, ALFWorld and WebShop with Qwen2.5-1.5B-Instruct and Qwen2.5-7B-Instruct, show that HGPO significantly outperforms existing agentic RL methods under the same computational constraints. Code is available at https://github.com/langfengQ/verl-agent/tree/master/recipe/hgpo.

## Key Ideas

> _Pending LLM analysis_

## Notes

