---
id: card-concept-median-robustness
kind: concept
name: 中位数稳健性
summary: 中位数对极端值稳健，右偏分布应优先报告中位数。
aliases:
- median
- 中位数
tags:
- 统计
claims:
- id: c1
  text: 均值对极端值敏感，中位数对极端值稳健。
  sources:
  - source: src-stats-notes
    loc: extracted/text.md#L4-L4
    span_sha256: 311dda09aaadf8b57fac860ebe82b21f52fac43aaae2bd7e7e72e6c237479ac0
- id: c2
  text: 收入、房价等右偏分布的集中趋势应优先报告中位数。
  sources:
  - source: src-stats-notes
    loc: extracted/text.md#L5-L5
    span_sha256: a88dca3d15db854b860e247dce4f5be1590c3111f26af265ae0a4e19a514e939
version: 1
status: active
schema_version: '0.1'
---

## 是什么

中位数是排序后位于中间位置的取值，单个极端值几乎不影响它，因此比均值稳健。

## 何时用

分布右偏或含离群点的集中趋势汇报：收入、房价、响应时延等。

## 怎么用

同时计算均值与中位数，两者差距大即提示偏态；对外口径优先中位数并说明。

## 边界与陷阱

中位数对分布形状不敏感，必要时配合分位数或直方图一起呈现。

## 关联

极端值的另一常见来源见「幸存者偏差」。
