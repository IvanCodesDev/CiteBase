---
id: card-concept-card-claim
kind: concept
name: 卡片与论断双粒度
summary: 卡片面向人的阅读与检索；论断面向机器的出处绑定、哈希核验与状态流转。
aliases:
- dual granularity
- 双粒度
- claim
tags:
- 架构
links:
- predicate: related_to
  to: card-method-span-provenance
claims:
- id: c1
  text: 知识单元是卡片与论断双粒度：卡片面向人的阅读与检索，论断面向机器的出处绑定、哈希核验、状态流转与矛盾裁决。
  sources:
  - source: src-design-notes
    loc: extracted/text.md#L7-L7
    span_sha256: 6c2d1be9d4f47fb3f8016f8bcf518cf97577f2d887fd5dd3c73c79a1e857556e
- id: c2
  text: 每条论断绑定源位置与内容哈希，quote 时重读源文本并重算哈希，源片段被改动无法静默通过。
  sources:
  - source: src-design-notes
    loc: extracted/text.md#L8-L8
    span_sha256: 45161cbfca6a9c1902988e4b21d74fe978f06a7d5cc2bd6cf663351e81b3f3d0
version: 1
status: active
schema_version: '0.1'
---

## 是什么

一张卡片同时承载两层结构：Markdown 正文供人阅读，frontmatter 里的结构化论断（claims）供机器逐条核验。

## 为什么

页面可以整体重写，论断不行——每条论断有自己的出处、哈希、状态与审计史，这让「说过什么、依据是什么」可以逐条追责。

## 边界

论断只记录可绑定出处的事实；无出处的推断进不了论断列表（会被质量闸拒绝）。

## 关联

出处绑定与核验的操作方式见「论断出处绑定与核验」。
