from __future__ import annotations

from pathlib import Path

from citebase import lint as lint_mod
from citebase.lint import Finding
from citebase.vault import Vault
from helpers import base_meta, make_claim, make_vault, write_card


def _lint(root: Path) -> list[Finding]:
    return lint_mod.lint_vault(Vault.load(root))


def _rules(findings: list[Finding]) -> set[str]:
    return {f.rule for f in findings}


def test_valid_vault_passes(mini_vault: Path) -> None:
    write_card(
        mini_vault,
        base_meta(
            claims=[make_claim()],
            links=[{"predicate": "related_to", "to": "card-concept-beta"}],
        ),
    )
    write_card(mini_vault, base_meta("card-concept-beta", name="Beta"))
    assert _lint(mini_vault) == []


def test_unknown_source_is_l_prov_1(mini_vault: Path) -> None:
    write_card(mini_vault, base_meta(claims=[make_claim(source="src-ghost")]))
    assert "L-PROV-1" in _rules(_lint(mini_vault))


def test_wrong_hash_is_l_prov_2(mini_vault: Path) -> None:
    write_card(mini_vault, base_meta(claims=[make_claim(sha="a" * 64)]))
    findings = _lint(mini_vault)
    assert "L-PROV-2" in _rules(findings)
    assert any("不一致" in f.message for f in findings)


def test_unresolvable_span_is_l_prov_2(mini_vault: Path) -> None:
    write_card(
        mini_vault,
        base_meta(claims=[make_claim(loc="extracted/text.md#L1-L99", sha="a" * 64)]),
    )
    assert "L-PROV-2" in _rules(_lint(mini_vault))


def test_unknown_kind_is_l_pack_1(mini_vault: Path) -> None:
    write_card(mini_vault, base_meta(kind="theorem"))
    assert "L-PACK-1" in _rules(_lint(mini_vault))


def test_unknown_predicate_is_l_link_1(mini_vault: Path) -> None:
    write_card(
        mini_vault,
        base_meta(links=[{"predicate": "loves", "to": "card-concept-beta"}]),
    )
    write_card(mini_vault, base_meta("card-concept-beta", name="Beta"))
    assert "L-LINK-1" in _rules(_lint(mini_vault))


def test_missing_link_target_is_l_link_1(mini_vault: Path) -> None:
    write_card(
        mini_vault,
        base_meta(links=[{"predicate": "related_to", "to": "card-concept-ghost"}]),
    )
    findings = _lint(mini_vault)
    assert "L-LINK-1" in _rules(findings)
    assert any("不存在" in f.message for f in findings)


def test_active_linking_terminal_is_l_life_1(mini_vault: Path) -> None:
    write_card(
        mini_vault,
        base_meta(links=[{"predicate": "related_to", "to": "card-concept-beta"}]),
    )
    write_card(mini_vault, base_meta("card-concept-beta", name="Beta", status="retired"))
    assert "L-LIFE-1" in _rules(_lint(mini_vault))


def test_supersedes_may_point_to_terminal(mini_vault: Path) -> None:
    write_card(
        mini_vault,
        base_meta(links=[{"predicate": "supersedes", "to": "card-concept-beta"}]),
    )
    write_card(mini_vault, base_meta("card-concept-beta", name="Beta", status="superseded"))
    assert _lint(mini_vault) == []


def test_duplicate_claim_ids_is_l_id_1(mini_vault: Path) -> None:
    write_card(
        mini_vault,
        base_meta(
            claims=[
                make_claim(cid="c1"),
                make_claim("第二行事实。", "extracted/text.md#L2-L2", cid="c1"),
            ]
        ),
    )
    assert "L-ID-1" in _rules(_lint(mini_vault))


def test_long_summary_is_l_sum_1(mini_vault: Path) -> None:
    write_card(mini_vault, base_meta(summary="长" * 81))
    assert "L-SUM-1" in _rules(_lint(mini_vault))


def test_federation_separator_in_id_is_l_id_1(mini_vault: Path) -> None:
    write_card(mini_vault, base_meta("card-concept-a::b"), relpath="cards/concept/fed.md")
    assert "L-ID-1" in _rules(_lint(mini_vault))


def test_undeclared_federation_link_is_l_fed_1_error(mini_vault: Path) -> None:
    """M5 起 L-FED-1 正式接管 M0 的 L-FED-0 占位：未声明依赖的跨库引用是 error。"""
    write_card(
        mini_vault,
        base_meta(links=[{"predicate": "related_to", "to": "other-vault::card-concept-x"}]),
    )
    findings = _lint(mini_vault)
    fed = [f for f in findings if f.rule == "L-FED-1"]
    assert fed and all(f.level == lint_mod.LEVEL_ERROR for f in fed)
    assert "L-LINK-1" not in _rules(findings)


def test_low_confidence_requires_flag(tmp_path: Path) -> None:
    root = make_vault(tmp_path / "v", confidence=0.4)
    write_card(root, base_meta(claims=[make_claim()]))
    findings = _lint(root)
    assert "L-PROV-4" in _rules(findings)
    assert all(f.level == lint_mod.LEVEL_WARN for f in findings)


def test_low_confidence_flag_silences_warn(tmp_path: Path) -> None:
    root = make_vault(tmp_path / "v", confidence=0.4)
    write_card(root, base_meta(claims=[make_claim(low_confidence=True)]))
    assert _lint(root) == []


def test_load_errors_surface_as_findings(mini_vault: Path) -> None:
    (mini_vault / "cards").mkdir(exist_ok=True)
    (mini_vault / "cards" / "broken.md").write_text("没有 frontmatter", encoding="utf-8")
    findings = _lint(mini_vault)
    assert "LOAD" in _rules(findings)


def test_has_errors_ignores_warnings() -> None:
    warn = Finding("L-PROV-4", lint_mod.LEVEL_WARN, "p", "m")
    err = Finding("L-PROV-1", lint_mod.LEVEL_ERROR, "p", "m")
    assert not lint_mod.has_errors([warn])
    assert lint_mod.has_errors([warn, err])
