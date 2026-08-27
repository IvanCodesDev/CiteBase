---
id: card-method-k-fold-cv
kind: method
name: k 折交叉验证
summary: 数据分 k 份轮流做验证集，评估方差比单次划分更小。
aliases:
- k-fold
- 交叉验证
- cross validation
tags:
- 机器学习
- 统计
links:
- predicate: pitfall
  to: card-pitfall-ts-cv-time-order
claims:
- id: c1
  text: k 折交叉验证把数据分成 k 份轮流做验证集，比单次划分的评估方差更小。
  sources:
  - source: src-ml-notes
    loc: extracted/text.md#L8-L8
    span_sha256: 76f53361c078ef04a0686dc6131025fb3e0807738ec4b983452c9f750142c104
version: 1
status: active
schema_version: '0.1'
---

## 是什么

把数据均分为 k 份，轮流取一份做验证、其余做训练，汇总 k 次评估结果。

## 何时用

数据量有限、单次划分评估波动大，需要更稳的泛化估计或超参数选择时。

## 怎么用

常用 k=5 或 10；分类任务用分层抽样保持类别比例；汇报均值与标准差。

## 边界与陷阱

时间序列不能随机切分（见陷阱链接）；预处理必须放进每折内部，避免泄漏。

## 关联

时间序列场景的专属陷阱见「时间序列交叉验证乱序」。
