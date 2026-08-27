---
id: card-pitfall-sync-retry-storm
kind: pitfall
name: 同步重试风暴
summary: 大量客户端同步重试造成级联过载的故障模式（联邦示例上游卡）。
aliases:
- retry storm
- 重试风暴
tags:
- 工程实践
claims:
- id: c1
  text: 重试风暴是大量客户端同步重试造成的级联过载。
  sources:
  - source: src-notes
    loc: extracted/text.md#L2-L2
    span_sha256: 66a526a816cc9da784e327623b66d8ca9bcf4f478155796508d4ca65ade0c856
version: 1
status: active
schema_version: '0.1'
---

## 现象

依赖短暂抖动后，流量瞬时数倍放大，下游被重试流量压垮。

## 根因

大量客户端使用相同的固定重试间隔，失败后同步发起重试。

## 规避

指数退避 + 随机抖动 + 最大尝试次数；服务端配合限流与快速失败。

## 触发条件

同构客户端 + 固定重试间隔 + 共享依赖故障。

## 关联

规避方法见「带抖动的指数退避」。
