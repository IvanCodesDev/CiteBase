---
id: card-concept-content-addressing
kind: concept
name: 内容寻址
summary: 用内容哈希作为标识的存储方式，天然去重且可校验完整性。
aliases:
- content addressing
- CAS
tags:
- 工程实践
claims:
- id: c1
  text: 内容寻址存储用内容哈希作为标识，天然去重且可校验完整性。
  sources:
  - source: src-eng-notes
    loc: extracted/text.md#L16-L16
    span_sha256: 7b6758dd0e75de4a42ed2d8965ff48de2f442e3385940fd632f6e6bcb2c378ff
version: 1
status: active
schema_version: '0.1'
---

## 是什么

以内容本身的哈希值作为对象标识的存储组织方式：相同内容必然同址，不同内容必然异址。

## 何时用

制品库、数据集版本化、备份系统等需要去重与完整性校验的场景。

## 怎么用

写入时计算内容哈希作为键；读取时按键取回并重算哈希校验完整性。

## 边界与陷阱

内容可变的对象不适合直接内容寻址，需要在其上再建一层可变引用（如 git 的 ref）。

## 关联

git 对象库与本项目的 span 哈希校验都是内容寻址思想的应用。
