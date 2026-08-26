---
id: card-method-windows-ci
kind: method
name: Windows 平台 CI 约定
summary: 设 PYTHONIOENCODING=utf-8、质量门拆单命令 step、提交信息走 stdin、行尾统一 LF。
aliases:
- PYTHONIOENCODING
- pwsh
- Windows CI
tags:
- 工程实践
links:
- predicate: related_to
  to: card-method-quality-gates-ci
claims:
- id: c1
  text: CI 必须设置 PYTHONIOENCODING=utf-8，否则 Windows 运行器上的中文输出会因 GBK 控制台编码报 UnicodeEncodeError。
  sources:
  - source: src-dev-log
    loc: extracted/text.md#L19-L19
    span_sha256: af0472192cb3d0f0a8268b8db846c655a0168991c857c56308c28efb64531c1d
- id: c2
  text: GitHub Actions 的 Windows 默认 shell 是 pwsh，多行 run 不会因中间某行失败而中断，质量门必须拆成单命令 step。
  sources:
  - source: src-dev-log
    loc: extracted/text.md#L20-L20
    span_sha256: 5787d570bccfb246ca291b49984560e00b9f0f9befe239c12dffcb6415d0cd5f
- id: c3
  text: PowerShell 不支持 bash 的 heredoc 语法，多行提交信息要用 here-string 经 stdin 传给 git commit -F -。
  sources:
  - source: src-dev-log
    loc: extracted/text.md#L21-L21
    span_sha256: c306f0f580540962abcc426a49760141706ed71b7d64da193d3cb6843a0291fe
- id: c4
  text: 仓库统一用 .gitattributes 归一化行尾，Windows 工作区的 CRLF 在提交时转换为 LF。
  sources:
  - source: src-dev-log
    loc: extracted/text.md#L22-L22
    span_sha256: 064d592a54760ef75efa9d0aff8fcc21b45c272236e8394bd1b790733ca99bd8
version: 1
status: active
schema_version: '0.1'
---

## 是什么

本仓库在 Windows 平台（本地开发与 CI 运行器）沉淀下来的四条工程约定：控制台编码、CI step 拆分、提交信息传递、行尾归一化。

## 何时用

编写或修改 CI 工作流、在 Windows 上执行 git 提交、以及排查「仅 Windows 平台失败」类问题时。

## 怎么用

工作流 env 里声明 `PYTHONIOENCODING: utf-8`；每道质量门一个 step；多行提交信息用 here-string 管道给 `git commit -F -`；`.gitattributes` 声明文本文件 eol=lf。

## 边界与陷阱

pwsh 的「多行 run 中间失败不中断」与 bash 语义相反，最容易造成假绿；PowerShell 里混用 bash heredoc 会直接解析错误。

## 关联

这些约定服务的整体质量闸见「CI 六道质量门」。
