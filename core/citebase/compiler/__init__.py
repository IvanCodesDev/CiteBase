"""编译器（L1）：唯一会调用 LLM 的子包；core 的 lint / index / search 全程无 LLM。"""

from citebase.compiler.pipeline import CompileReport, compile_vault
from citebase.compiler.providers import ScriptedLlmProvider, load_scripted
from citebase.compiler.review import approve, load_queue, reject

__all__ = [
    "CompileReport",
    "ScriptedLlmProvider",
    "approve",
    "compile_vault",
    "load_queue",
    "load_scripted",
    "reject",
]
