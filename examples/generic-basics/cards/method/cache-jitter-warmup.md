---
id: card-method-cache-jitter-warmup
kind: method
name: 过期抖动与热点预热
summary: 用随机过期抖动和热点预热分散缓存失效时刻的缓解手段。
aliases:
- 缓存过期抖动
- 热点预热
tags:
- 工程实践
links:
- predicate: related_to
  to: card-pitfall-cache-avalanche
claims:
- id: c1
  text: 给过期时间加随机抖动与热点数据预热是缓解缓存雪崩的常用手段。
  sources:
  - source: src-eng-notes
    loc: extracted/text.md#L13-L13
    span_sha256: d863ef4cbd8e64fdd22abe3fba369523dc17c87ff16755a5e75c48496d87586f
version: 1
status: active
schema_version: '0.1'
---

## 是什么

两个互补动作：写缓存时给过期时间叠加随机偏移，把失效时刻打散；对已知热点在失效前主动回填。

## 何时用

批量写入缓存、定时刷新缓存，或热点集中的读多写少场景。

## 怎么用

过期时间 = 基准值 ± 随机抖动（如 ±10%）；热点键由访问统计识别，过期前异步预热。

## 边界与陷阱

抖动幅度过小起不到打散作用；预热本身也要限流，避免预热流量冲击后端。

## 关联

对应故障模式见「缓存雪崩」。
