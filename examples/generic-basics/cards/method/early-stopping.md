---
id: card-method-early-stopping
kind: method
name: 早停
summary: 验证指标不再改善时提前终止训练以控制过拟合。
aliases:
- early stopping
tags:
- 机器学习
links:
- predicate: related_to
  to: card-pitfall-overfitting
claims:
- id: c1
  text: 早停是控制过拟合的常用手段之一。
  sources:
  - source: src-ml-notes
    loc: extracted/text.md#L5-L5
    span_sha256: bc8383acedce574c8e2c4612fb715c857c2904f651312db9b106c2ac576f2c01
version: 1
status: active
schema_version: '0.1'
---

## 是什么

训练时持续监控验证集指标，连续若干轮不再改善即停止，回退到历史最优权重。

## 何时用

迭代式训练（梯度下降、boosting）且能划出可信验证集时。

## 怎么用

设定监控指标、耐心值（patience）与最小改善阈值；停止后加载最优轮次的模型。

## 边界与陷阱

验证集太小会让早停信号抖动；耐心值过小会过早停止在局部波动上。

## 关联

针对的故障模式见「过拟合」。
