"""Vault 联邦（M5）：依赖锁定、跨库引用、联邦检索、过期提示与四条不变量。"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from cardvault import cli
from cardvault import lint as lint_mod
from cardvault.federation import (
    PATH_DEP_REV,
    FederationError,
    card_hashes,
    deps_status,
    deps_sync,
    federated_follow,
    federated_quote,
    federated_read,
    load_lock,
    root_hash,
    search_scoped,
)
from cardvault.mcp.server import read_impl, search_impl
from cardvault.model import DepSpec
from cardvault.vault import Vault
from helpers import REPO_ROOT, base_meta, make_claim, make_vault, write_card
from pydantic import ValidationError

ALPHA = "card-concept-alpha"
LOCAL = "card-concept-local"
FED_ALPHA = f"provider::{ALPHA}"


def _provider(tmp_path: Path) -> Path:
    root = make_vault(tmp_path / "provider")
    write_card(root, base_meta(aliases=["alpha"], claims=[make_claim()]))
    return root


def _consumer(tmp_path: Path, *, link_to: str = FED_ALPHA) -> Path:
    root = make_vault(tmp_path / "consumer")
    (root / "vault.yaml").write_text(
        "name: consumer\npacks: [testpack]\ndeps:\n  provider:\n    path: ../provider\n",
        encoding="utf-8",
    )
    write_card(
        root,
        base_meta(
            LOCAL,
            name="Local",
            links=[{"predicate": "related_to", "to": link_to}],
        ),
    )
    return root


def _pair(tmp_path: Path, **consumer_kwargs: str) -> tuple[Path, Path]:
    provider = _provider(tmp_path)
    consumer = _consumer(tmp_path, **consumer_kwargs)
    return provider, consumer


def test_dep_spec_validation() -> None:
    assert DepSpec(path="../x").path == "../x"
    assert DepSpec(git="https://x/y", rev="abc").rev == "abc"
    with pytest.raises(ValidationError, match="之一"):
        DepSpec()
    with pytest.raises(ValidationError, match="之一"):
        DepSpec(git="https://x/y", path="../x", rev="abc")
    with pytest.raises(ValidationError, match="rev"):
        DepSpec(git="https://x/y")


def test_deps_sync_writes_deterministic_lock(tmp_path: Path) -> None:
    _, consumer = _pair(tmp_path)

    report = deps_sync(consumer)

    assert report.synced == ["provider"]
    lock = load_lock(consumer)
    entry = lock["provider"]
    assert entry["resolved_rev"] == PATH_DEP_REV
    assert entry["root_hash"].startswith("sha256:")
    assert ALPHA in entry["cards"]

    first = (consumer / "vault.lock").read_bytes()
    deps_sync(consumer)
    assert (consumer / "vault.lock").read_bytes() == first


def test_card_hashes_newline_insensitive(tmp_path: Path) -> None:
    """同一依赖库的 CRLF 检出与 LF 检出应产生相同锁哈希（跨平台可复现）。"""
    lf_root = _provider(tmp_path / "lf")
    crlf_root = _provider(tmp_path / "crlf")
    for root, sep in ((lf_root, b"\n"), (crlf_root, b"\r\n")):
        for md in sorted(root.rglob("*.md")):
            data = md.read_bytes().replace(b"\r\n", b"\n")
            md.write_bytes(data.replace(b"\n", sep))

    lf_hashes = card_hashes(lf_root)
    crlf_hashes = card_hashes(crlf_root)

    assert lf_hashes == crlf_hashes
    assert root_hash(lf_hashes) == root_hash(crlf_hashes)


def test_deps_sync_reports_upgrade_impact(tmp_path: Path) -> None:
    provider, consumer = _pair(tmp_path)
    deps_sync(consumer)

    card_path = provider / "cards" / "concept" / f"{ALPHA}.md"
    card_path.write_text(
        card_path.read_text(encoding="utf-8") + "\n上游追加了一段正文。\n",
        encoding="utf-8",
    )
    report = deps_sync(consumer)

    assert len(report.impacts) == 1
    impact = report.impacts[0]
    assert impact.changed == [ALPHA]
    assert impact.affected_local == [LOCAL]  # 升级影响面：本库哪些卡引用了变更卡


def test_deps_status_lifecycle(tmp_path: Path) -> None:
    provider, consumer = _pair(tmp_path)

    before = deps_status(consumer)
    assert [d.state for d in before.deps] == ["needs_sync"]
    assert not before.clean

    deps_sync(consumer)
    clean = deps_status(consumer)
    assert [d.state for d in clean.deps] == ["ok"]
    assert clean.clean

    card_path = provider / "cards" / "concept" / f"{ALPHA}.md"
    card_path.write_text(
        card_path.read_text(encoding="utf-8") + "\n上游又改了。\n", encoding="utf-8"
    )
    stale = deps_status(consumer)
    assert [d.state for d in stale.deps] == ["stale"]  # 依赖过期提示，而非本库 suspect
    assert not stale.clean


def test_deps_status_flags_broken_and_terminal_refs(tmp_path: Path) -> None:
    provider, consumer = _pair(tmp_path, link_to="provider::card-concept-ghost")
    deps_sync(consumer)
    ghost = deps_status(consumer)
    assert ghost.deps[0].broken_refs == [f"{LOCAL} → provider::card-concept-ghost"]

    write_card(
        provider,
        base_meta("card-concept-old", name="Old", status="retired", claims=[make_claim()]),
    )
    (consumer / "cards" / "concept" / f"{LOCAL}.md").unlink()
    write_card(
        consumer,
        base_meta(
            LOCAL,
            name="Local",
            links=[{"predicate": "related_to", "to": "provider::card-concept-old"}],
        ),
    )
    deps_sync(consumer)
    report = deps_status(consumer)
    assert report.deps[0].terminal_refs
    assert "retired" in report.deps[0].terminal_refs[0]


def test_lint_federation_rules(tmp_path: Path) -> None:
    provider, consumer = _pair(tmp_path)

    def rules(root: Path) -> dict[str, str]:
        return {
            f.rule: f.level for f in lint_mod.lint_vault(Vault.load(root)) if "FED" in f.rule
        }

    # 未 sync：L-FED-3（链接级 + vault 级）
    assert rules(consumer) == {"L-FED-3": "error"}

    deps_sync(consumer)
    assert rules(consumer) == {}  # 锁定一致且目标存在：零联邦告警

    # 未声明的依赖 → L-FED-1
    (consumer / "cards" / "concept" / f"{LOCAL}.md").unlink()
    write_card(
        consumer,
        base_meta(
            LOCAL, name="Local", links=[{"predicate": "related_to", "to": "ghost::card-x"}]
        ),
    )
    assert rules(consumer) == {"L-FED-1": "error"}

    # 上游目标不存在 → L-FED-1；上游终态 → L-FED-2 warn
    (consumer / "cards" / "concept" / f"{LOCAL}.md").unlink()
    write_card(
        consumer,
        base_meta(
            LOCAL,
            name="Local",
            links=[{"predicate": "related_to", "to": "provider::card-concept-ghost"}],
        ),
    )
    assert rules(consumer) == {"L-FED-1": "error"}

    write_card(
        provider,
        base_meta("card-concept-old", name="Old", status="retired", claims=[make_claim()]),
    )
    deps_sync(consumer)
    (consumer / "cards" / "concept" / f"{LOCAL}.md").unlink()
    write_card(
        consumer,
        base_meta(
            LOCAL,
            name="Local",
            links=[{"predicate": "related_to", "to": "provider::card-concept-old"}],
        ),
    )
    assert rules(consumer) == {"L-FED-2": "warn"}


def test_scoped_search_annotates_and_defaults_to_self(tmp_path: Path) -> None:
    _, consumer = _pair(tmp_path)
    deps_sync(consumer)

    self_only = search_scoped(consumer, "alpha")
    assert self_only["hit"] is False  # 默认只搜本库：上游内容不可见（M0 行为不变）

    fed = search_scoped(consumer, "alpha", scope=["self", "provider"])
    assert fed["hit"] is True
    hit = fed["hits"][0]
    assert hit["id"] == FED_ALPHA
    assert hit["vault"] == "provider"

    with pytest.raises(FederationError, match="未声明"):
        search_scoped(consumer, "alpha", scope=["self", "ghost"])


def test_federated_read_quote_follow(tmp_path: Path) -> None:
    provider, consumer = _pair(tmp_path)
    write_card(
        provider,
        base_meta(
            "card-method-beta",
            kind="method",
            name="Beta",
            links=[{"predicate": "related_to", "to": ALPHA}],
            claims=[make_claim("第二行事实。", "extracted/text.md#L2-L2", cid="c1")],
        ),
    )
    deps_sync(consumer)

    card = federated_read(consumer, FED_ALPHA)
    assert card is not None and card.meta.id == ALPHA
    assert federated_read(consumer, "provider::card-ghost") is None

    quote = federated_quote(consumer, f"{FED_ALPHA}#c1")
    assert quote is not None
    assert quote.card_id == FED_ALPHA
    assert quote.spans[0].verified is True  # 不变量 1：出处链跨库仍可验证

    edges = federated_follow(consumer, "provider::card-method-beta")
    assert edges is not None
    assert edges["out"][0]["card"] == FED_ALPHA  # 邻居 id 保持可继续跳读

    with pytest.raises(FederationError, match=r"未锁定|未声明"):
        federated_read(tmp_path / "consumer", "ghost::card-x")


def test_mcp_impls_support_federation(tmp_path: Path) -> None:
    _, consumer = _pair(tmp_path)
    deps_sync(consumer)

    result = search_impl(consumer, "alpha", scope=["self", "provider"])
    assert result["hit"] is True
    assert result["hits"][0]["vault"] == "provider"

    payload = read_impl(consumer, FED_ALPHA)
    assert payload["found"] is True
    assert payload["id"] == ALPHA

    missing = read_impl(consumer, "ghost::card-x")
    assert missing["found"] is False
    assert "未声明" in missing["hint"]


def test_deps_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, consumer = _pair(tmp_path)

    assert cli.main(["deps", "status", "--vault", str(consumer)]) == 1
    assert "needs_sync" in capsys.readouterr().out

    assert cli.main(["deps", "sync", "--vault", str(consumer)]) == 0
    assert "已锁定 1 个依赖" in capsys.readouterr().out

    assert cli.main(["deps", "status", "--vault", str(consumer)]) == 0
    assert "全部依赖锁定一致" in capsys.readouterr().out

    assert (
        cli.main(
            ["search", "alpha", "--scope", "self", "--scope", "provider",
             "--vault", str(consumer)]
        )
        == 0
    )
    assert "←provider" in capsys.readouterr().out


@pytest.mark.skipif(shutil.which("git") is None, reason="需要 git 可执行文件")
def test_git_dep_resolution_offline(tmp_path: Path) -> None:
    """git 依赖离线验证：本地裸路径 clone + rev 锁定（不触网）。"""
    provider = _provider(tmp_path)
    env_args = ["-c", "user.name=cardvault-test", "-c", "user.email=test@local"]
    subprocess.run(["git", "init", "--quiet"], cwd=provider, check=True)
    subprocess.run(["git", "add", "-A"], cwd=provider, check=True)
    subprocess.run(
        ["git", *env_args, "commit", "--quiet", "-m", "init"], cwd=provider, check=True
    )
    rev = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=provider, check=True,
        capture_output=True, text=True,
    ).stdout.strip()

    consumer = make_vault(tmp_path / "consumer")
    provider_url = str(provider.resolve()).replace("\\", "/")
    (consumer / "vault.yaml").write_text(
        "name: consumer\npacks: [testpack]\ndeps:\n  provider:\n"
        f"    git: {provider_url}\n    rev: {rev}\n",
        encoding="utf-8",
    )
    report = deps_sync(consumer)

    assert report.synced == ["provider"]
    assert load_lock(consumer)["provider"]["resolved_rev"] == rev
    assert (consumer / "_deps" / "provider" / "vault.yaml").is_file()
    assert deps_status(consumer).clean


def test_federation_example_reproducible() -> None:
    """M5 验收线：双库联邦示例可复现（lock 已提交，检索/取引/lint 全通）。"""
    consumer = REPO_ROOT / "examples" / "federation" / "consumer"
    if not consumer.is_dir():  # pragma: no cover - 示例被移除时此测试才跳过
        pytest.skip("联邦示例不存在")

    errors = [
        f for f in lint_mod.lint_vault(Vault.load(consumer)) if f.level == lint_mod.LEVEL_ERROR
    ]
    assert errors == []
    assert deps_status(consumer).clean

    fed = search_scoped(consumer, "退避", scope=["self", "methods-provider"])
    assert fed["hit"] is True
    assert any(h["vault"] == "methods-provider" for h in fed["hits"])

    quote = federated_quote(
        consumer, "methods-provider::card-method-backoff-with-jitter#c1"
    )
    assert quote is not None
    assert all(span.verified for span in quote.spans)
