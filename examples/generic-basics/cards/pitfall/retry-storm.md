---
id: card-pitfall-retry-storm
kind: pitfall
name: 重试风暴
summary: 大量客户端同步重试压垮下游、把局部故障放大的现象。
aliases:
- retry storm
tags:
- 工程实践
links:
- predicate: related_to
  to: card-method-exponential-backoff
claims:
- id: c1
  text: 无上限的重试会放大故障，必须设置最大尝试次数与总时长预算。
  sources:
  - source: src-eng-notes
    loc: extracted/text.md#L9-L9
    span_sha256: ff717e3853ab846a41eeb3b70bad65fa829d593cb30b107e19969864327626dd
- id: c2
  text: 配合抖动的指数退避可避免重试风暴。
  sources:
  - source: src-eng-notes
    loc: extracted/text.md#L8-L8
    span_sha256: 3aa9d5ab168ab879e92aefa09917926b1307acb9c7c02629e2492dbea7b35da0
version: 1
status: active
schema_version: '0.1'
---

## 现象

下游短暂抖动后流量不降反升，重试流量叠加正常流量把服务彻底压垮，故障时间被显著拉长。

## 根因

大量客户端在相同节奏上无上限重试：失败越多重试越多，形成正反馈。

## 规避

指数退避 + 随机抖动打散重试节奏；设置最大尝试次数与总时长预算；必要时熔断。

## 触发条件

下游出现瞬时不可用，且调用方重试无退避或无上限。

## 关联

规避方法见「指数退避」。
