# 更新日志

本项目所有值得注意的变更都记录在本文件中。

格式基于 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-CN/1.1.0/),
版本号遵循[语义化版本 2.0.0](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added

- **M0 规格与骨架**:冻结 card / evidence-event / pack 三类 JSON Schema v0.1 作为契约事实源。
- **M0**:`vault lint / index / search / read / quote / follow` 命令行工作流,内核全程无 LLM。
- **M1 编译循环**:七步编译管线(file/dir 适配器 + plain/pypdf 抽取器),产出一律进入人工审核队列,`_compile_log` 逐次留痕模型/成本/产出。
- **M1**:内置 scripted 与 OpenAI 兼容两个 LlmProvider;compiler 是唯一调用 LLM 的子包。
- **M2 治理 + MCP**:`drift / audit / resolve` 治理动词与失效信号总线(双通道漂移 + 时效)。
- **M2**:只读四工具 MCP Server(stdio,可选依赖 `cardvault[mcp]`)。
- **M2**:`vault init` 脚手架——空 vault + generic 包 + CI 即治理模板。
- **M3 证据回流 + 评测**:EvidenceEvent 事件源与确定性回流编译器(失败聚类 → 陷阱卡草案)。
- **M3**:可复算的知识贡献度榜单(负贡献进复核候选)与检索日志缺口清单。
- **M3**:忠实度抽查(哈希通道 + 人工核对清单)。
- **M4 加速与导出**:SQLite 索引后端,对照测试保证与内存后端检索结果逐分一致。
- **M4**:site 静态站点与 json 确定性快照两个导出器(附许可证警示)。
- **M4**:bench 检索性能基线(合成 N 卡、双后端 P50/P95)。
- **M5 Vault 联邦**:deps 依赖声明与 vault.lock 锁定(resolved_rev + 逐卡内容哈希)。
- **M5**:`::` 跨库引用与联邦检索 scope,附依赖过期提示。
