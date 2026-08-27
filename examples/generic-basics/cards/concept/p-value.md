---
id: card-concept-p-value
kind: concept
name: p 值
summary: 原假设为真时观察到当前或更极端数据的概率。
aliases:
- p-value
- p值
tags:
- 统计
links:
- predicate: related_to
  to: card-pitfall-multiple-comparison
claims:
- id: c1
  text: p 值是在原假设为真时观察到当前或更极端数据的概率，不是原假设为真的概率。
  sources:
  - source: src-stats-notes
    loc: extracted/text.md#L12-L12
    span_sha256: 2c35fb26d1a4cf5333cb3ccca4169e4ef44db2c849ee2b6d679cb24f98e716e1
version: 1
status: active
schema_version: '0.1'
---

## 是什么

假设检验的证据度量：在原假设成立的前提下，数据至少与观测同样极端的概率。

## 何时用

对照实验或抽样比较需要量化「差异是否超出随机波动」时。

## 怎么用

事先设定显著性水平并固定分析方案；p 值与效应量、置信区间一起汇报。

## 边界与陷阱

p 值不是原假设为真的概率；大样本下微小无意义差异也会显著。

## 关联

反复检验的陷阱见「多重比较」。
