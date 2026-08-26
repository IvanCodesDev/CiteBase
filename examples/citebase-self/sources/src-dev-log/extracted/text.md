# Citebase 开发事件日志（工程事实）

## 2026-08-28 项目更名 CardVault → CiteBase

整仓更名后，虚拟环境里的可编辑安装仍指向更名前的旧目录，导致 pytest 报 ModuleNotFoundError: No module named 'citebase'。
可编辑安装（pip install -e）在 site-packages 里写的是绝对路径，项目目录改名后必须重新安装一次才能生效。
更名残留最容易漏在被 gitignore 的本地配置里：.cursor/mcp.json 与 .codex/config.toml 的 --workspace 参数曾指向旧路径。
排查更名残留要用 --no-ignore 连同被忽略文件一起全库搜索，普通搜索默认跳过 gitignore 覆盖的文件。

## 2026-08-28 CI mypy 因 mcp 类型存根漂移失败

CI 全新安装拿到 mcp 2.1.1 而本地 venv 是 2.0.0：mcp.server.fastmcp 模块存根在 2.1.1 重新出现，但不再暴露 FastMCP 属性。
挂在兼容回退 import 上的 type: ignore[import-not-found] 注释随依赖存根形态漂移，反过来变成 unused-ignore 报错。
修复方式：主路径静态导入 MCPServer 保持类型完整，旧版回退分支改用 importlib 动态导入 + cast，与类型存根彻底解耦。
教训：随第三方存根形态变化的 type: ignore 注释本质不稳定；本地依赖版本要与 CI 全新安装对齐，否则本地绿、CI 红。

## Windows 平台工程约定

CI 必须设置 PYTHONIOENCODING=utf-8，否则 Windows 运行器上的中文输出会因 GBK 控制台编码报 UnicodeEncodeError。
GitHub Actions 的 Windows 默认 shell 是 pwsh，多行 run 不会因中间某行失败而中断，质量门必须拆成单命令 step。
PowerShell 不支持 bash 的 heredoc 语法，多行提交信息要用 here-string 经 stdin 传给 git commit -F -。
仓库统一用 .gitattributes 归一化行尾，Windows 工作区的 CRLF 在提交时转换为 LF。
