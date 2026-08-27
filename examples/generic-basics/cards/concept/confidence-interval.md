---
id: card-concept-confidence-interval
kind: concept
name: 置信区间
summary: 重复抽样中约 95% 的区间会覆盖真值的区间估计。
aliases:
- confidence interval
tags:
- 统计
links:
- predicate: related_to
  to: card-method-bootstrap
claims:
- id: c1
  text: 95% 置信区间的含义是重复抽样中约 95% 的区间会覆盖真值。
  sources:
  - source: src-stats-notes
    loc: extracted/text.md#L16-L16
    span_sha256: 17071334fbf74a17f6ee20d6f14d9989c27fdc3b28884b2d13fc052b2cd7a5a2
version: 1
status: active
schema_version: '0.1'
---

## 是什么

对总体参数的区间估计：按同样流程重复抽样，约 95% 的区间会覆盖真值。

## 何时用

汇报估计量的不确定性，替代只报一个点估计。

## 怎么用

解析公式或自助法构造；汇报时同时给出点估计与区间端点。

## 边界与陷阱

「95% 概率真值在这个区间里」是常见误读；区间宽度受样本量与方差共同影响。

## 关联

小样本下的构造方法见「自助法」。
