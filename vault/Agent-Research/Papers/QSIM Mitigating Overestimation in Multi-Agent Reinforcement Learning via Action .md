---
title: QSIM: Mitigating Overestimation in Multi-Agent Reinforcement Learning via Action Similarity Weighted Q-Learning
authors: [Yuanjun Li, Bin Zhang, Hao Chen, Zhouyang Jiang, Dapeng Li]
arxiv_id: 2602.22786v1
published: 2026-02-26T09:20:46+00:00
pdf_url: https://arxiv.org/pdf/2602.22786v1
categories: [cs.MA, cs.AI, cs.LG]
tags: [#paper, #arxiv, #ai-research]
created: 2026-03-01
---

# QSIM: Mitigating Overestimation in Multi-Agent Reinforcement Learning via Action Similarity Weighted Q-Learning

**Authors:** Yuanjun Li, Bin Zhang, Hao Chen, Zhouyang Jiang, Dapeng Li…
**Published:** 2026-02-26T09:20:46+00:00
**PDF:** [Link](https://arxiv.org/pdf/2602.22786v1)
**Categories:** cs.MA, cs.AI, cs.LG

## Abstract

Value decomposition (VD) methods have achieved remarkable success in cooperative multi-agent reinforcement learning (MARL). However, their reliance on the max operator for temporal-difference (TD) target calculation leads to systematic Q-value overestimation. This issue is particularly severe in MARL due to the combinatorial explosion of the joint action space, which often results in unstable learning and suboptimal policies. To address this problem, we propose QSIM, a similarity weighted Q-learning framework that reconstructs the TD target using action similarity. Instead of using the greedy joint action directly, QSIM forms a similarity weighted expectation over a structured near-greedy joint action space. This formulation allows the target to integrate Q-values from diverse yet behaviorally related actions while assigning greater influence to those that are more similar to the greedy choice. By smoothing the target with structurally relevant alternatives, QSIM effectively mitigates overestimation and improves learning stability. Extensive experiments demonstrate that QSIM can be seamlessly integrated with various VD methods, consistently yielding superior performance and stability compared to the original algorithms. Furthermore, empirical analysis confirms that QSIM significantly mitigates the systematic value overestimation in MARL. Code is available at https://github.com/MaoMaoLYJ/pymarl-qsim.

## Key Ideas

> _Pending LLM analysis_

## Notes

