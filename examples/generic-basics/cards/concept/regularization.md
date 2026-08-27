---
id: card-concept-regularization
kind: concept
name: 正则化
summary: 通过约束模型复杂度抑制过拟合的一类技术。
aliases:
- regularization
tags:
- 机器学习
links:
- predicate: related_to
  to: card-pitfall-overfitting
claims:
- id: c1
  text: 正则化是控制过拟合的常用手段之一。
  sources:
  - source: src-ml-notes
    loc: extracted/text.md#L5-L5
    span_sha256: bc8383acedce574c8e2c4612fb715c857c2904f651312db9b106c2ac576f2c01
version: 1
status: active
schema_version: '0.1'
---

## 是什么

在损失函数或训练过程中加入对模型复杂度的惩罚（如 L1/L2、dropout），换取更好的泛化。

## 何时用

模型在训练集与验证集表现分叉、参数量相对数据量偏大时。

## 怎么用

从弱正则开始逐步加强，用验证集指标选择强度；不同族模型选用匹配的正则形式。

## 边界与陷阱

正则过强会欠拟合；正则强度是超参数，须与其他超参数一起搜索。

## 关联

针对的故障模式见「过拟合」。
