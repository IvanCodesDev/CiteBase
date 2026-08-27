---
id: card-pitfall-data-leakage
kind: pitfall
name: 数据泄漏
summary: 训练特征混入目标信息，线下指标虚高而线上失效。
aliases:
- data leakage
tags:
- 机器学习
links:
- predicate: related_to
  to: card-method-k-fold-cv
claims:
- id: c1
  text: 数据泄漏指训练特征中混入了目标变量的信息，导致线下指标虚高而线上失效。
  sources:
  - source: src-ml-notes
    loc: extracted/text.md#L12-L12
    span_sha256: 4e4fcd3f647391b5eadbcc64f8423c960841a98cfa925f494b91ded26a954e69
- id: c2
  text: 在划分训练与测试集之前做全量标准化或特征选择是常见的泄漏来源。
  sources:
  - source: src-ml-notes
    loc: extracted/text.md#L13-L13
    span_sha256: c52a60e5d92aa6b146e71c526fc8d9996d201d549d93e9894a831310a43e2652
version: 1
status: active
schema_version: '0.1'
---

## 现象

线下评估接近完美，上线后效果断崖式下跌。

## 根因

特征工程或预处理动用了目标变量信息，或在划分数据前对全量数据做了统计。

## 规避

一切统计量只在训练折内计算；用管道把预处理绑定进交叉验证；上线前做时间外推校验。

## 触发条件

划分前的全量标准化/特征选择、含未来信息的特征、目标编码不当。

## 关联

时间维度的特例见「时间序列交叉验证乱序」。
