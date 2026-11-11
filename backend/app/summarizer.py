"""LLM-generated plain-English summaries for files, functions and classes.

Summaries are cached in SQLite keyed by a hash of exactly what would be sent
to the model (node kind + source text) plus the model name. Unchanged code is
never re-summarized, even across re-analyses of the same repo or across repos
that happen to contain identical code; edited code hashes differently and gets
a fresh summary.
"""
import hashlib
import os
from dataclasses import dataclass

from app.db import get_node, get_related, get_summary, save_summary
from app.repo_service import SCRATCH_DIR

DEFAULT_MODEL = "claude-haiku-5-5"
MAX_SOURCE_CHARS = 12_000  # keep prompts (and cost) bounded for very large files


class SummarizerError(Exception):
    """Raised for user-facing problems (missing API key, missing source, ...)."""


@dataclass
class SummaryResult:
    summary: str
    cached: bool
    model: str


def get_model() -> str:
    return os.environ.get("SUMMARY_MODEL", DEFAULT_MODEL)


def content_hash(node_type: str, source: str) -> str:
    return hashlib.sha256(f"{node_type}\n{source}".encode("utf-8")).hexdigest()


def load_source(repo_id: str, node: dict) -> str:
    """Read the source text a node covers from the cloned repo on disk."""
    path = node.get("path")
    if not path:
        raise SummarizerError("This node has no source file.")
    root = (SCRATCH_DIR / repo_id).resolve()
    file_path = (root / path).resolve()
    if root not in file_path.parents or not file_path.is_file():
        raise SummarizerError(
            "Source not found on disk. Re-run the analysis for this repository."
        )
    text = file_path.read_text(encoding="utf-8", errors="replace")
    if node["node_type"] in ("Function", "Class") and node.get("start_line"):
        lines = text.splitlines()
        text = "\n".join(lines[node["start_line"] - 1 : node["end_line"]])
    return text[:MAX_SOURCE_CHARS]


def _build_prompt(node: dict, source: str, context: str) -> str:
    kind = node["node_type"].lower()
    return (
        f"Explain this Python {kind} in plain English for a developer who is new to the "
        f"codebase. Use 2-4 sentences: what it is for, how it works at a high level, and "
        f"how it fits in with its surroundings. Do not restate the code line by line.\n\n"
        f"Name: {node['name']}\nFile: {node['path']}\n{context}\n"
        f"<code>\n{source}\n</code>"
    )


def _relationship_context(repo_id: str, node: dict) -> str:
    # Relationship context is a hint only; it is deliberately not part of the cache
    # key so graph tweaks don't invalidate summaries of unchanged code.
    def names(edge_type: str, direction: str) -> str:
        found = get_related(repo_id, node["id"], edge_type, direction)
        return ", ".join(n["name"] for n in found[:15]) or "none"

    if node["node_type"] == "File":
        return (
            f"Defines: {names('DEFINES', 'out')}\n"
            f"Imports: {names('IMPORTS', 'out')}\n"
            f"Imported by: {names('IMPORTS', 'in')}"
        )
    return f"Calls: {names('CALLS', 'out')}\nCalled by: {names('CALLS', 'in')}"


def cached_summary(repo_id: str, node_id: str) -> SummaryResult | None:
    """Return an existing summary without ever calling the LLM."""
    node = get_node(repo_id, node_id)
    if not node:
        return None
    try:
        source = load_source(repo_id, node)
    except SummarizerError:
        return None
    model = get_model()
    hit = get_summary(content_hash(node["node_type"], source), model)
    return SummaryResult(summary=hit, cached=True, model=model) if hit else None


def summarize_node(repo_id: str, node_id: str, client=None) -> SummaryResult:
    """Return a summary for a node, calling the LLM only on a cache miss."""
    node = get_node(repo_id, node_id)
    if not node:
        raise SummarizerError(f"Unknown node: {node_id}")

    source = load_source(repo_id, node)
    if not source.strip():
        raise SummarizerError("Nothing to summarize: the source is empty.")

    model = get_model()
    key = content_hash(node["node_type"], source)
    hit = get_summary(key, model)
    if hit:
        return SummaryResult(summary=hit, cached=True, model=model)

    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SummarizerError(
                "ANTHROPIC_API_KEY is not set. Export it before starting the backend "
                "to enable summaries."
            )
        import anthropic

        client = anthropic.Anthropic()

    prompt = _build_prompt(node, source, _relationship_context(repo_id, node))
    response = client.messages.create(
        model=model,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text").strip()
    if not text:
        raise SummarizerError("The model returned an empty summary.")

    save_summary(key, model, text)
    return SummaryResult(summary=text, cached=False, model=model)
