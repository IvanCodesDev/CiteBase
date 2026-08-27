---
id: card-concept-simple-baseline
kind: concept
name: 简单基线优先
summary: 先跑简单基线再上复杂模型的建模次序原则。
aliases:
- baseline first
- 基线优先
tags:
- 机器学习
- 时间序列
links:
- predicate: related_to
  to: card-method-moving-average
claims:
- id: c1
  text: 小样本单调趋势序列可先尝试简单基线再考虑复杂模型。
  sources:
  - source: src-ml-notes
    loc: extracted/text.md#L20-L20
    span_sha256: 5be065ef5b86d5a741be8880c89b3ba90e21114b6f10fedc22f7aad206547083
version: 1
status: active
schema_version: '0.1'
---

## 是什么

一条建模次序原则：任何复杂模型上场前，先建立最简单的可解释基线并记录其成绩。

## 何时用

所有预测/分类任务的起步阶段，尤其是小样本场景。

## 怎么用

选一个零成本基线（均值、上期值、移动平均），复杂模型只有显著超过基线才被采纳。

## 边界与陷阱

没有基线对照的「提升」无法归因；基线也要用与正式模型相同的评估协议。

## 关联

常用基线之一见「移动平均」。
