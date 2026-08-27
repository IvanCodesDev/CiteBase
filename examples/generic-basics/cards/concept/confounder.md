---
id: card-concept-confounder
kind: concept
name: 混杂变量
summary: 同时影响两个变量、制造虚假相关的第三变量。
aliases:
- confounder
- 混杂因素
tags:
- 统计
links:
- predicate: related_to
  to: card-pitfall-correlation-causation
claims:
- id: c1
  text: 混杂变量可以让两个无因果关系的变量表现出高相关。
  sources:
  - source: src-stats-notes
    loc: extracted/text.md#L9-L9
    span_sha256: e7ad9ad32d1847e9e1096566eecc6302cd7304f197f3dac5543d7c6e87bba4c4
version: 1
status: active
schema_version: '0.1'
---

## 是什么

同时影响自变量与因变量的第三变量；不加控制时会在两者之间制造虚假关联。

## 何时用

任何基于观察性数据的关联分析都应先列混杂变量清单。

## 怎么用

分层分析、回归控制、匹配或随机化，把候选混杂纳入模型或设计。

## 边界与陷阱

控制「碰撞变量」反而会引入偏差；混杂识别依赖领域知识而非纯统计。

## 关联

对应错误结论模式见「相关不等于因果」。
