---
id: card-concept-suspect-lifecycle
kind: concept
name: 失效治理生命周期
summary: drift 只把受影响卡标为 suspect 并退出检索；改写与裁决永远由人完成。
aliases:
- suspect
- 漂移治理
- drift
tags:
- 治理
links:
- predicate: related_to
  to: card-concept-retrieval-funnel
claims:
- id: c1
  text: drift 聚合源修订变化、span 哈希不匹配与时效过期信号，只把受影响卡片标记为 suspect，从不自动改写或删除知识。
  sources:
  - source: src-design-notes
    loc: extracted/text.md#L24-L24
    span_sha256: 482f591e38f7210a65406a7cc4237c39156a7f49fd316dd27878e260f3a282b5
- id: c2
  text: 机器提出并拦截，人来裁决：无出处论断被质量闸拒绝；矛盾、合并候选与 suspect 卡进入人工工作流。
  sources:
  - source: src-design-notes
    loc: extracted/text.md#L25-L25
    span_sha256: f814bedb062845efbd0ac11b743364f61a70e84f94fb6a5a09d2f2a7a11623b0
- id: c3
  text: 矛盾卡由编译器检测并记录，但哪一方正确永远由人工 resolve 裁决。
  sources:
  - source: src-design-notes
    loc: extracted/text.md#L26-L26
    span_sha256: a8b82b1c0b312d44ce29267cd64d82057f69468f6a30732fb5b682b6aa000ffc
version: 1
status: active
schema_version: '0.1'
---

## 是什么

知识失效不是删除，而是状态流转：源漂移、哈希不匹配、时效过期都只产生 suspect 标记，卡片默认退出检索等待人工复核。

## 为什么

自动改写的质量上限就是幻觉率；机器负责发现与拦截，人负责最终裁决，这是质量闸的分工设计。

## 边界

drift 不会自愈；suspect 卡需要人工 audit review 才能回到 active 或走向终态。

## 关联

suspect 卡如何影响检索结果见「检索漏斗」。
