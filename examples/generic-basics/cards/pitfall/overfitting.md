---
id: card-pitfall-overfitting
kind: pitfall
name: 过拟合
summary: 模型记住训练集细节导致泛化能力下降的现象。
aliases:
- overfitting
tags:
- 机器学习
links:
- predicate: related_to
  to: card-method-early-stopping
- predicate: related_to
  to: card-concept-regularization
claims:
- id: c1
  text: 过拟合表现为训练误差持续下降而验证误差开始上升。
  sources:
  - source: src-ml-notes
    loc: extracted/text.md#L4-L4
    span_sha256: f58f3c296635cd549867d2939269b6eabd585f70fc51239be314ded4832d51ba
- id: c2
  text: 正则化、早停和数据增强是控制过拟合的常用手段。
  sources:
  - source: src-ml-notes
    loc: extracted/text.md#L5-L5
    span_sha256: bc8383acedce574c8e2c4612fb715c857c2904f651312db9b106c2ac576f2c01
version: 1
status: active
schema_version: '0.1'
---

## 现象

训练集指标持续变好，验证集指标先好转后回落，两条曲线分叉。

## 根因

模型容量相对数据量过大，把训练集中的噪声当成了规律。

## 规避

正则化、早停、数据增强；更根本的是增加数据或降低模型容量。

## 触发条件

小数据 + 大模型 + 训练轮数过多。

## 关联

控制手段见「正则化」「早停」。
