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
- **M2**:只读四工具 MCP Server(stdio,可选依赖 `citebase[mcp]`)。
- **M2**:`vault init` 脚手架——空 vault + generic 包 + CI 即治理模板。
- **M3 证据回流 + 评测**:EvidenceEvent 事件源与确定性回流编译器(失败聚类 → 陷阱卡草案)。
- **M3**:可复算的知识贡献度榜单(负贡献进复核候选)与检索日志缺口清单。
- **M3**:忠实度抽查(哈希通道 + 人工核对清单)。
- **M4 加速与导出**:SQLite 索引后端,对照测试保证与内存后端检索结果逐分一致。
- **M4**:site 静态站点与 json 确定性快照两个导出器(附许可证警示)。
- **M4**:bench 检索性能基线(合成 N 卡、双后端 P50/P95)。
- **M5 Vault 联邦**:deps 依赖声明与 vault.lock 锁定(resolved_rev + 逐卡内容哈希)。
- **M5**:`::` 跨库引用与联邦检索 scope,附依赖过期提示。
- **自举 vault**:`examples/citebase-self` 用 Citebase 管理 Citebase 自身的工程知识
  (概念/方法/决策/陷阱四类 14 卡,论断全部绑定 span 哈希),接入 CI 三道质量门。
- `scripts/refresh_span_hashes.py`:手工撰写卡片的 span 哈希占位回填工具
  (只填 PENDING 占位,不改写已有哈希,不掩盖漂移)。
- pre-commit 提交规范钩子(`.githooks/` + `scripts/install-hooks.sh`):
  强制提交身份,拦截 docs/、缓存与本地配置入库。

### Changed

- 项目更名:CardVault → Citebase(包名 `citebase`,CLI 入口 `vault` / `vault-mcp` 不变)。
- CI 示例库 index 步骤升级为 `vault index --check`(L-IDX-1 索引一致性核验)。
- README / PROJECT_STRUCTURE / spec README 不再链接私有 docs/ 目录,设计与工程知识改由自举 vault 公开。

### Fixed

- MCP 服务器类解析与 mcp 2.1.1 类型存根解耦(旧版回退分支改
  importlib 动态导入 + cast),消除随依赖存根形态漂移的 mypy 报错。
