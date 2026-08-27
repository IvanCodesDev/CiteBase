---
id: card-pitfall-ts-cv-time-order
kind: pitfall
name: 时间序列交叉验证乱序
summary: 对时间序列随机切分交叉验证，等于用未来数据预测过去。
aliases:
- 时间序列泄漏
tags:
- 机器学习
- 时间序列
links:
- predicate: refines
  to: card-pitfall-data-leakage
claims:
- id: c1
  text: 时间序列数据做交叉验证必须保持时间顺序，禁止用未来数据训练预测过去。
  sources:
  - source: src-ml-notes
    loc: extracted/text.md#L9-L9
    span_sha256: 7ea40cf2e22fb51263123f542296c25b45e11ae509d9b67b587be6c3fba702df
version: 1
status: active
schema_version: '0.1'
---

## 现象

交叉验证指标非常好，上线后对真实未来的预测明显变差。

## 根因

随机切分让训练集中混入了验证时点之后的数据，模型「偷看」了未来。

## 规避

使用按时间滚动的展开式划分（train 只含验证窗之前的数据）。

## 触发条件

数据带时间戳且分布随时间漂移，却使用了随机 k 折。

## 关联

它是「数据泄漏」在时间维度上的特例。
