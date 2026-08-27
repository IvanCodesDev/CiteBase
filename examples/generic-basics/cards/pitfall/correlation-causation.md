---
id: card-pitfall-correlation-causation
kind: pitfall
name: 相关不等于因果
summary: 相关系数只度量线性关联，高相关不能证明因果关系。
aliases:
- correlation is not causation
tags:
- 统计
links:
- predicate: related_to
  to: card-concept-confounder
claims:
- id: c1
  text: 相关系数只度量线性关联强度，不能证明因果关系。
  sources:
  - source: src-stats-notes
    loc: extracted/text.md#L8-L8
    span_sha256: cde2d5917d26b9db4ee942ed51d8da76c501df3c6350a750678babb6356d7f41
- id: c2
  text: 混杂变量可以让两个无因果关系的变量表现出高相关。
  sources:
  - source: src-stats-notes
    loc: extracted/text.md#L9-L9
    span_sha256: e7ad9ad32d1847e9e1096566eecc6302cd7304f197f3dac5543d7c6e87bba4c4
version: 1
status: active
schema_version: '0.1'
---

## 现象

由「X 与 Y 高度相关」直接得出「X 导致 Y」的结论，干预 X 后 Y 并未如预期变化。

## 根因

相关只刻画共变，因果需要排除混杂、反向因果与巧合。

## 规避

寻找混杂变量并控制；有条件做随机实验或使用因果推断方法。

## 触发条件

观察性数据 + 业务压力下的快速归因。

## 关联

最常见的干扰来源见「混杂变量」。
