---
id: card-method-moving-average
kind: method
name: 移动平均
summary: 平稳序列短期平滑预测基线，窗口越大越平滑但滞后越明显。
aliases:
- moving average
tags:
- 时间序列
links:
- predicate: related_to
  to: card-concept-simple-baseline
claims:
- id: c1
  text: 移动平均适合平稳序列的短期平滑预测，窗口越大越平滑但滞后越明显。
  sources:
  - source: src-ml-notes
    loc: extracted/text.md#L19-L19
    span_sha256: 0b1b496765795b517304f352cd6430ff6d2d51c2c199ab83fa5f4bfede6d26f2
version: 1
status: active
schema_version: '0.1'
---

## 是什么

取最近 w 个观测的平均值作为平滑值或下一步预测值的经典时间序列基线。

## 何时用

序列大致平稳、需要快速给出可解释基线或平滑噪声时。

## 怎么用

按验证误差选窗口 w；作为后续复杂模型的对照基线保留在报告中。

## 边界与陷阱

窗口越大滞后越明显；对趋势和季节性序列会系统性偏差，需先差分或换模型。

## 关联

方法选型次序见「简单基线优先」。
