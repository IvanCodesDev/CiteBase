---
id: card-concept-idempotency
kind: concept
name: 幂等性
summary: 重复执行效果与执行一次相同的操作性质，是安全重试的前提。
aliases:
- idempotency
- 幂等
tags:
- 工程实践
links:
- predicate: related_to
  to: card-method-exponential-backoff
claims:
- id: c1
  text: 幂等操作重复执行的效果与执行一次相同，是安全重试的前提。
  sources:
  - source: src-eng-notes
    loc: extracted/text.md#L4-L4
    span_sha256: ee66f97d9969bacdc1d0afe0193abd4b6fc142e6ad3f4d01387f2cb5f2cf9e5b
- id: c2
  text: 网络请求的幂等性通常靠客户端生成的幂等键实现。
  sources:
  - source: src-eng-notes
    loc: extracted/text.md#L5-L5
    span_sha256: cd218c928e903081ce6d013876ac5640a734ac2c174f929ae6806f1cf2867adc
version: 1
status: active
schema_version: '0.1'
---

## 是什么

幂等性描述这样一类操作：执行一次与重复执行多次，对系统状态的最终影响完全相同。

## 何时用

任何可能失败后重试的写操作：网络请求、消息消费、任务投递、支付扣款。

## 怎么用

由客户端为每次业务意图生成唯一幂等键，服务端按键去重；同键请求返回首次执行的结果。

## 边界与陷阱

幂等键的作用域与有效期需要显式设计；只对「同一意图」去重，不同意图复用键会吞掉合法请求。

## 关联

重试策略（指数退避）依赖幂等性才安全，见链接卡片。
