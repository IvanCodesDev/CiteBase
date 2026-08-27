---
id: card-method-backoff-with-jitter
kind: method
name: 带抖动的指数退避
summary: 指数退避叠加随机抖动的重试节流方法（联邦示例上游卡）。
aliases:
- backoff with jitter
- 抖动退避
tags:
- 工程实践
links:
- predicate: pitfall
  to: card-pitfall-sync-retry-storm
claims:
- id: c1
  text: 指数退避在每次失败后成倍拉长重试等待时间。
  sources:
  - source: src-notes
    loc: extracted/text.md#L1-L1
    span_sha256: e6d421242fc3e60b7e88f13f58bdc0c015bfd4b7990ef0c326814d187a94aad0
- id: c2
  text: 在退避间隔上叠加随机抖动可以打散同步重试波峰。
  sources:
  - source: src-notes
    loc: extracted/text.md#L3-L3
    span_sha256: 50cea187990d42f91b9fe5bdaef0c35519ca2d1910fa45fbcfeccd72f3405ef5
version: 1
status: active
schema_version: '0.1'
---

## 是什么

重试节流策略：失败后等待时间指数增长，并在间隔上叠加随机抖动。

## 何时用

调用不稳定外部依赖且操作幂等时；多客户端同时消费同一依赖时抖动尤其重要。

## 怎么用

设定基础间隔、倍率、抖动幅度、最大尝试次数与总时长预算；超出预算快速失败。

## 边界与陷阱

被重试操作必须幂等；不加抖动的指数退避仍可能形成同步波峰。

## 关联

对应故障模式见「同步重试风暴」。
