"""编译期注入扫描（威胁模型 §2-①）：检出源派生物中的「指令样文本」。

规则库版本化（RULES_VERSION），随编译器更新；扫描结果进 _compile_log 与
injection_risk 旗标。诚实声明：这是缓解不是根治——最终执行决策在宿主 Agent，
Citebase 的责任是不放大攻击面：可疑区段不进验证链（L-SEC-1）、不隐瞒风险标记。
"""

from __future__ import annotations

import re

RULES_VERSION = "sec-rules@1"

#: 指令样文本模式：提示词劫持、角色扮演劫持、工具调用诱导（中英双语）。
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore-instructions",
        re.compile(
            r"(ignore|disregard|forget)\s+(all\s+)?(previous|prior|above|earlier)"
            r"\s+(instructions?|prompts?|rules?)",
            re.IGNORECASE,
        ),
    ),
    (
        "reveal-system-prompt",
        re.compile(
            r"(reveal|print|show|repeat)\s+(your\s+)?(system\s+prompt|initial\s+instructions?)",
            re.IGNORECASE,
        ),
    ),
    ("role-hijack-en", re.compile(r"\byou\s+are\s+now\s+(a|an|the|in)\b", re.IGNORECASE)),
    ("new-instructions", re.compile(r"\b(new|updated)\s+instructions?\s*:", re.IGNORECASE)),
    (
        "tool-injection",
        re.compile(
            r"(call|invoke|execute)\s+(the\s+)?(tool|function|command)\s",
            re.IGNORECASE,
        ),
    ),
    ("do-anything-now", re.compile(r"\bDAN\s+mode\b|\bdo\s+anything\s+now\b", re.IGNORECASE)),
    (
        "ignore-instructions-zh",
        re.compile(r"忽略(之前|以上|上面|先前)的?(所有|全部)?(指令|提示|规则|设定)"),
    ),
    ("role-hijack-zh", re.compile(r"(现在开始|从现在起)你(是|扮演|作为)")),
    ("reveal-prompt-zh", re.compile(r"(输出|打印|重复|泄露)你的(系统提示|初始指令|提示词)")),
    ("tool-injection-zh", re.compile(r"(调用|执行)(工具|函数|命令|shell)")),
]


def scan_text(text: str) -> list[str]:
    """返回命中的规则名列表（去重、按规则表顺序）。"""
    hits: list[str] = []
    for name, pattern in _PATTERNS:
        if pattern.search(text):
            hits.append(name)
    return hits
