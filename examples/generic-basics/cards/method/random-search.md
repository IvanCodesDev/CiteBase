---
id: card-method-random-search
kind: method
name: 随机搜索
summary: 高维超参数空间中通常比网格搜索更高效的调参方法。
aliases:
- random search
tags:
- 机器学习
links:
- predicate: related_to
  to: card-method-k-fold-cv
claims:
- id: c1
  text: 网格搜索在低维超参数空间可行，高维时随机搜索通常更高效。
  sources:
  - source: src-ml-notes
    loc: extracted/text.md#L16-L16
    span_sha256: a21f753fbb98e9c6bc0d1d1ce5f4929ae522faeb2eb5dcd3f23a7b340f6ae2e4
version: 1
status: active
schema_version: '0.1'
---

## 是什么

在超参数空间内按给定分布随机采样若干组合并逐一评估，取最优。

## 何时用

超参数超过两三个、且各参数重要性未知时；预算固定要求可控评估次数时。

## 怎么用

对数尺度参数用对数均匀分布采样；固定评估预算；配合交叉验证评估每组。

## 边界与陷阱

采样数太少时结论不稳定；连续调优可升级到贝叶斯优化。

## 关联

评估配套见「k 折交叉验证」。
