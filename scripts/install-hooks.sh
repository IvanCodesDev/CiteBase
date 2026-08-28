#!/bin/sh
# 安装 CiteBase 版本化 git 钩子到本地 .git/hooks。
# 用法(仓库根目录执行): sh scripts/install-hooks.sh
set -eu

repo_root="$(git rev-parse --show-toplevel)"
src="$repo_root/.githooks"
dst="$repo_root/.git/hooks"

for hook in "$src"/*; do
	name="$(basename "$hook")"
	cp "$hook" "$dst/$name"
	chmod +x "$dst/$name"
	echo "已安装钩子: $name"
done

echo "完成。也可改用: git config core.hooksPath .githooks"
