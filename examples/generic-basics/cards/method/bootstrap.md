---
id: card-method-bootstrap
kind: method
name: 自助法
summary: 有放回重抽样估计抽样分布，适用小样本且分布未知场景。
aliases:
- bootstrap
- 自助抽样
tags:
- 统计
links:
- predicate: related_to
  to: card-concept-confidence-interval
claims:
- id: c1
  text: 自助法通过有放回重抽样估计统计量的抽样分布，适用于小样本且分布未知的场景。
  sources:
  - source: src-stats-notes
    loc: extracted/text.md#L17-L17
    span_sha256: fbebb2f8fa3564064cbf828a427771e75e63775e87a69bc44edfe336934c5502
version: 1
status: active
schema_version: '0.1'
---

## 是什么

从样本中有放回地重抽样出大量副本，用副本上统计量的分布近似其抽样分布。

## 何时用

样本小、目标统计量没有解析分布（中位数、分位数、复杂指标）时。

## 怎么用

重抽样 1000 次以上，每次计算目标统计量，用分位数法构造置信区间。

## 边界与陷阱

对极值类统计量效果差；时间序列需用块自助法保持依赖结构。

## 关联

典型用途见「置信区间」。
