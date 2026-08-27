---
id: card-pitfall-cache-avalanche
kind: pitfall
name: 缓存雪崩
summary: 大量缓存同时失效导致请求全部打到后端存储的故障模式。
aliases:
- cache avalanche
tags:
- 工程实践
links:
- predicate: related_to
  to: card-method-cache-jitter-warmup
claims:
- id: c1
  text: 缓存雪崩指大量缓存同时失效导致请求全部打到后端存储。
  sources:
  - source: src-eng-notes
    loc: extracted/text.md#L12-L12
    span_sha256: 56f5f8b6221d24992de66c79de6610098083b4fe1ee3cc0c994e4fffc731decc
- id: c2
  text: 给过期时间加随机抖动与热点数据预热是缓解缓存雪崩的常用手段。
  sources:
  - source: src-eng-notes
    loc: extracted/text.md#L13-L13
    span_sha256: d863ef4cbd8e64fdd22abe3fba369523dc17c87ff16755a5e75c48496d87586f
version: 1
status: active
schema_version: '0.1'
---

## 现象

缓存命中率断崖式下跌，后端存储 QPS 突增并伴随延迟飙升甚至宕机。

## 根因

大批缓存键使用相同或相近的过期时间，在同一时刻集中失效。

## 规避

过期时间叠加随机抖动、热点数据预热、后端限流兜底。

## 触发条件

批量写入缓存且过期时间一致，例如整点批量刷新。

## 关联

缓解手段见「过期抖动与热点预热」。
