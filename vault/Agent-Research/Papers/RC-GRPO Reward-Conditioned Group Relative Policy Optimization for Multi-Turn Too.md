---
title: RC-GRPO: Reward-Conditioned Group Relative Policy Optimization for Multi-Turn Tool Calling Agents
authors: [Haitian Zhong, Jixiu Zhai, Lei Song, Jiang Bian, Qiang Liu]
arxiv_id: 2602.03025v1
published: 2026-02-03T02:47:32+00:00
pdf_url: https://arxiv.org/pdf/2602.03025v1
categories: [cs.AI, cs.CL]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# RC-GRPO: Reward-Conditioned Group Relative Policy Optimization for Multi-Turn Tool Calling Agents

**Authors:** Haitian Zhong, Jixiu Zhai, Lei Song, Jiang Bian, Qiang Liu…
**Published:** 2026-02-03T02:47:32+00:00
**PDF:** [Link](https://arxiv.org/pdf/2602.03025v1)
**Categories:** cs.AI, cs.CL

## Abstract

Multi-turn tool calling is challenging for Large Language Models (LLMs) because rewards are sparse and exploration is expensive. A common recipe, SFT followed by GRPO, can stall when within-group reward variation is low (e.g., more rollouts in a group receive the all 0 or all 1 reward), making the group-normalized advantage uninformative and yielding vanishing updates. To address this problem, we propose RC-GRPO (Reward-Conditioned Group Relative Policy Optimization), which treats exploration as a controllable steering problem via discrete reward tokens. We first fine-tune a Reward-Conditioned Trajectory Policy (RCTP) on mixed-quality trajectories with reward goal special tokens (e.g., <|high_reward|>, <|low_reward|>) injected into the prompts, enabling the model to learn how to generate distinct quality trajectories on demand. Then during RL, we sample diverse reward tokens within each GRPO group and condition rollouts on the sampled token to improve within-group diversity, improving advantage gains. On the Berkeley Function Calling Leaderboard v4 (BFCLv4) multi-turn benchmark, our method yields consistently improved performance than baselines, and the performance on Qwen-2.5-7B-Instruct even surpasses all closed-source API models.

## Key Ideas

> _Pending LLM analysis_

## Notes

