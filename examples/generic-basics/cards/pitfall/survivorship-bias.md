---
id: card-pitfall-survivorship-bias
kind: pitfall
name: 幸存者偏差
summary: 只分析通过筛选的样本导致的系统性错误。
aliases:
- survivorship bias
tags:
- 统计
links:
- predicate: related_to
  to: card-pitfall-simpsons-paradox
claims:
- id: c1
  text: 幸存者偏差指只分析通过筛选的样本而忽略未通过者导致的系统性错误。
  sources:
  - source: src-stats-notes
    loc: extracted/text.md#L20-L20
    span_sha256: 04639bf35bb14282f0af786d68622a58d0be457689520ccb648c25d5d6f0125d
version: 1
status: active
schema_version: '0.1'
---

## 现象

基于「留存下来」的样本得出规律，推广到全体后失效，甚至方向相反。

## 根因

进入分析的数据经历了隐含筛选，未通过筛选的个体系统性缺席。

## 规避

追问「数据是怎么来的」，补齐或建模缺席样本；对留存人群单独声明结论边界。

## 触发条件

用户留存分析、成功案例复盘、二战轰炸机中弹分析等只见幸存者的场景。

## 关联

另一类分组统计陷阱见「辛普森悖论」。
