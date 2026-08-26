# Citebase 发布与仓库治理笔记

## 公开仓库边界

docs/ 设计文档目录不进入公开仓库：.gitignore 排除并已取消跟踪，公开知识经自举 vault 以卡片形式发布。
公开提交的作者与提交者身份固定为 IvanCodesDev，由 pre-commit 钩子强制校验。
pre-commit 钩子同时拦截 docs/、本地配置、缓存与生成物路径进入暂存区；版本化副本在 .githooks/，scripts/install-hooks.sh 一键安装。

## 质量门与 CI

CI 在 ubuntu 与 windows 双平台跑六道门：ruff、mypy（strict）、pytest、示例库 lint、index、eval。
vault 的 _index JSON 是提交物，一致性由 vault index --check 校验（L-IDX-1）；index.sqlite 是本地缓存不入库。
评测验收线：golden set 命中率与首位命中率都不得低于 0.8。

## 版本策略

CHANGELOG 遵循 Keep a Changelog 1.1.0，版本号遵循语义化版本 2.0.0。
schema 版本与代码版本解耦独立演进，破坏性变更必须附迁移脚本。
