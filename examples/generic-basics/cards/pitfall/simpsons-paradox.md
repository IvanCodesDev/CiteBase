---
id: card-pitfall-simpsons-paradox
kind: pitfall
name: 辛普森悖论
summary: 分组结论与合并结论方向相反，根因是组间权重差异。
aliases:
- simpsons paradox
- 辛普森
tags:
- 统计
links:
- predicate: related_to
  to: card-pitfall-survivorship-bias
claims:
- id: c1
  text: 辛普森悖论指分组结论与合并结论方向相反的现象，根因是组间权重差异。
  sources:
  - source: src-stats-notes
    loc: extracted/text.md#L21-L21
    span_sha256: 47304ce4f0ee8d6b6ef95223a2d522f59e2c9371ac1f3c8be4febbe873aff9ea
version: 1
status: active
schema_version: '0.1'
---

## 现象

每个分组里 A 都优于 B，合并后却是 B 优于 A（或反之）。

## 根因

各组样本权重悬殊，合并统计被大组主导，组间构成差异掩盖了组内趋势。

## 规避

汇报前检查关键维度的分组构成；用加权或标准化口径对齐后再比较。

## 触发条件

两组样本在关键混杂维度上的构成比例明显不同。

## 关联

同属统计口径陷阱，参见「幸存者偏差」。
