from pathlib import Path

import networkx as nx

from app.ast_parser import parse_file

IGNORED_DIRS = {".git", "venv", ".venv", "node_modules", "__pycache__", ".scratch"}


def _relevant_py_files(repo_root: Path) -> list[Path]:
    return [
        f
        for f in sorted(repo_root.rglob("*.py"))
        if not any(part in IGNORED_DIRS for part in f.relative_to(repo_root).parts)
    ]


def _module_index(py_files: list[Path], repo_root: Path) -> dict[str, Path]:
    """Map every dotted-suffix a file could be imported as to its path.

    e.g. backend/app/repo_service.py registers "backend.app.repo_service",
    "app.repo_service", and "repo_service" so imports resolve regardless of
    which directory is on sys.path.
    """
    index: dict[str, Path] = {}
    for f in py_files:
        parts = list(f.relative_to(repo_root).with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        for start in range(len(parts)):
            dotted = ".".join(parts[start:])
            if dotted:
                index.setdefault(dotted, f)
    return index


def build_graph(repo_root: Path) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    py_files = _relevant_py_files(repo_root)
    module_idx = _module_index(py_files, repo_root)

    parsed_by_file = {}
    function_name_idx: dict[str, list[str]] = {}
    class_name_idx: dict[str, str] = {}

    for f in py_files:
        rel = str(f.relative_to(repo_root))
        parsed = parse_file(f)
        parsed_by_file[f] = parsed

        file_id = f"file:{rel}"
        graph.add_node(file_id, type="File", name=rel, path=rel)

        for func in parsed.functions:
            func_id = f"function:{rel}::{func.qualname}"
            graph.add_node(
                func_id,
                type="Function",
                name=func.name,
                path=rel,
                start_line=func.start_line,
                end_line=func.end_line,
            )
            graph.add_edge(file_id, func_id, type="DEFINES")
            function_name_idx.setdefault(func.name, []).append(func_id)

        for cls in parsed.classes:
            class_id = f"class:{rel}::{cls.name}"
            graph.add_node(
                class_id,
                type="Class",
                name=cls.name,
                path=rel,
                start_line=cls.start_line,
                end_line=cls.end_line,
            )
            graph.add_edge(file_id, class_id, type="DEFINES")
            class_name_idx[cls.name] = class_id

    for f, parsed in parsed_by_file.items():
        rel = str(f.relative_to(repo_root))
        file_id = f"file:{rel}"

        for imp in parsed.imports:
            target_file = module_idx.get(imp.module)
            if target_file is None:
                for name in imp.names:
                    target_file = module_idx.get(f"{imp.module}.{name}")
                    if target_file:
                        break
            if target_file and target_file != f:
                target_id = f"file:{target_file.relative_to(repo_root)}"
                graph.add_edge(file_id, target_id, type="IMPORTS")

        local_functions = {func.name: f"function:{rel}::{func.qualname}" for func in parsed.functions}

        for func in parsed.functions:
            func_id = f"function:{rel}::{func.qualname}"
            for called_name in func.calls:
                target_id = local_functions.get(called_name)
                if target_id is None:
                    candidates = function_name_idx.get(called_name, [])
                    if len(candidates) == 1:
                        target_id = candidates[0]
                if target_id and target_id != func_id:
                    graph.add_edge(func_id, target_id, type="CALLS")

        for cls in parsed.classes:
            class_id = f"class:{rel}::{cls.name}"
            for base in cls.bases:
                target_id = class_name_idx.get(base)
                if target_id and target_id != class_id:
                    graph.add_edge(class_id, target_id, type="INHERITS")

    return graph


def graph_stats(graph: nx.MultiDiGraph) -> dict:
    by_type: dict[str, int] = {}
    for _, data in graph.nodes(data=True):
        by_type[data["type"]] = by_type.get(data["type"], 0) + 1
    return {
        "num_nodes": graph.number_of_nodes(),
        "num_edges": graph.number_of_edges(),
        "num_files": by_type.get("File", 0),
        "num_functions": by_type.get("Function", 0),
        "num_classes": by_type.get("Class", 0),
    }


def fan_in_out(graph: nx.MultiDiGraph, node_id: str) -> dict:
    return {"fan_in": graph.in_degree(node_id), "fan_out": graph.out_degree(node_id)}
