---
id: card-pitfall-multiple-comparison
kind: pitfall
name: 多重比较
summary: 多次假设检验使假阳性率累积，需要做校正。
aliases:
- multiple comparison
- 多重检验
tags:
- 统计
links:
- predicate: related_to
  to: card-concept-p-value
claims:
- id: c1
  text: 多次假设检验会使假阳性率累积，需要做多重比较校正。
  sources:
  - source: src-stats-notes
    loc: extracted/text.md#L13-L13
    span_sha256: 2e70179bde228af91431c51c4d5287db69ec4f5407857121d398686b86d376d9
version: 1
status: active
schema_version: '0.1'
---

## 现象

同时检验很多指标或分组，总能「发现」几个显著结果，但复现实验时消失。

## 根因

单次检验 5% 的假阳性率随检验次数累积，20 次检验期望出现一次假阳性。

## 规避

Bonferroni、FDR 等多重比较校正；预注册主要假设，探索性结果只作线索。

## 触发条件

指标看板扫差异、A/B 实验切多维分组、特征海选。

## 关联

基础概念见「p 值」。
