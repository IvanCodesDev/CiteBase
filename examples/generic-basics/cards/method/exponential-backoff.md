---
id: card-method-exponential-backoff
kind: method
name: 指数退避
summary: 失败后成倍拉长重试等待并叠加抖动的重试节流方法。
aliases:
- exponential backoff
- 退避重试
tags:
- 工程实践
links:
- predicate: related_to
  to: card-concept-idempotency
- predicate: pitfall
  to: card-pitfall-retry-storm
claims:
- id: c1
  text: 指数退避在每次失败后成倍拉长等待时间，配合抖动可避免重试风暴。
  sources:
  - source: src-eng-notes
    loc: extracted/text.md#L8-L8
    span_sha256: 3aa9d5ab168ab879e92aefa09917926b1307acb9c7c02629e2492dbea7b35da0
- id: c2
  text: 无上限的重试会放大故障，必须设置最大尝试次数与总时长预算。
  sources:
  - source: src-eng-notes
    loc: extracted/text.md#L9-L9
    span_sha256: ff717e3853ab846a41eeb3b70bad65fa829d593cb30b107e19969864327626dd
version: 1
status: active
schema_version: '0.1'
---

## 是什么

一种重试节流策略：第 n 次失败后的等待时间按指数增长（如 1s、2s、4s、8s），并叠加随机抖动。

## 何时用

调用不稳定的外部依赖（网络、第三方 API、队列消费）且操作幂等时。

## 怎么用

设定基础间隔、倍率、抖动幅度、最大尝试次数与总时长预算五个参数；超出预算即快速失败并上报。

## 边界与陷阱

被重试的操作必须幂等；不设上限的重试会把局部故障放大成全局故障。

## 关联

前提见「幂等性」；对应故障模式见「重试风暴」。
