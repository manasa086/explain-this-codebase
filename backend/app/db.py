import datetime
import sqlite3
from pathlib import Path

import networkx as nx

DB_PATH = Path(__file__).resolve().parent.parent / ".scratch" / "graph.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    analyzed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nodes (
    repo_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    path TEXT,
    start_line INTEGER,
    end_line INTEGER,
    PRIMARY KEY (repo_id, node_id)
);

CREATE TABLE IF NOT EXISTS edges (
    repo_id TEXT NOT NULL,
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS repo_files (
    repo_id TEXT NOT NULL,
    path TEXT NOT NULL,
    PRIMARY KEY (repo_id, path)
);

CREATE INDEX IF NOT EXISTS idx_edges_repo_source ON edges(repo_id, source);
CREATE INDEX IF NOT EXISTS idx_edges_repo_target ON edges(repo_id, target);
CREATE INDEX IF NOT EXISTS idx_nodes_repo_type ON nodes(repo_id, type);
"""


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def save_graph(repo_id: str, url: str, graph: nx.MultiDiGraph) -> None:
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM nodes WHERE repo_id = ?", (repo_id,))
        conn.execute("DELETE FROM edges WHERE repo_id = ?", (repo_id,))
        conn.execute(
            "INSERT OR REPLACE INTO repos (id, url, analyzed_at) VALUES (?, ?, ?)",
            (repo_id, url, datetime.datetime.utcnow().isoformat()),
        )
        conn.executemany(
            "INSERT INTO nodes (repo_id, node_id, type, name, path, start_line, end_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    repo_id,
                    node_id,
                    data.get("type"),
                    data.get("name"),
                    data.get("path"),
                    data.get("start_line"),
                    data.get("end_line"),
                )
                for node_id, data in graph.nodes(data=True)
            ],
        )
        conn.executemany(
            "INSERT INTO edges (repo_id, source, target, type) VALUES (?, ?, ?, ?)",
            [(repo_id, source, target, data.get("type")) for source, target, data in graph.edges(data=True)],
        )
    conn.close()


def save_files(repo_id: str, paths: list[str]) -> None:
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM repo_files WHERE repo_id = ?", (repo_id,))
        conn.executemany(
            "INSERT INTO repo_files (repo_id, path) VALUES (?, ?)",
            [(repo_id, p) for p in paths],
        )
    conn.close()


def get_files(repo_id: str) -> list[str]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT path FROM repo_files WHERE repo_id = ? ORDER BY path", (repo_id,)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_repo(repo_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT id, url, analyzed_at FROM repos WHERE id = ?", (repo_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "url": row[1], "analyzed_at": row[2]}


def get_stats(repo_id: str) -> dict:
    conn = get_connection()
    num_nodes = conn.execute("SELECT COUNT(*) FROM nodes WHERE repo_id = ?", (repo_id,)).fetchone()[0]
    num_edges = conn.execute("SELECT COUNT(*) FROM edges WHERE repo_id = ?", (repo_id,)).fetchone()[0]
    by_type = dict(
        conn.execute(
            "SELECT type, COUNT(*) FROM nodes WHERE repo_id = ? GROUP BY type", (repo_id,)
        ).fetchall()
    )
    conn.close()
    return {
        "num_nodes": num_nodes,
        "num_edges": num_edges,
        "num_files": by_type.get("File", 0),
        "num_functions": by_type.get("Function", 0),
        "num_classes": by_type.get("Class", 0),
    }


def _row_to_node(row) -> dict:
    return {
        "id": row[0],
        "node_type": row[1],
        "name": row[2],
        "path": row[3],
        "start_line": row[4],
        "end_line": row[5],
    }


def get_node(repo_id: str, node_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT node_id, type, name, path, start_line, end_line FROM nodes "
        "WHERE repo_id = ? AND node_id = ?",
        (repo_id, node_id),
    ).fetchone()
    conn.close()
    return _row_to_node(row) if row else None


def get_nodes_by_ids(repo_id: str, node_ids: list[str]) -> list[dict]:
    if not node_ids:
        return []
    conn = get_connection()
    placeholders = ",".join("?" for _ in node_ids)
    rows = conn.execute(
        f"SELECT node_id, type, name, path, start_line, end_line FROM nodes "
        f"WHERE repo_id = ? AND node_id IN ({placeholders})",
        (repo_id, *node_ids),
    ).fetchall()
    conn.close()
    by_id = {r[0]: _row_to_node(r) for r in rows}
    return [by_id[nid] for nid in node_ids if nid in by_id]


def search_nodes(repo_id: str, query: str, limit: int = 50) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT node_id, type, name, path, start_line, end_line FROM nodes "
        "WHERE repo_id = ? AND name LIKE ? ORDER BY name LIMIT ?",
        (repo_id, f"%{query}%", limit),
    ).fetchall()
    conn.close()
    return [_row_to_node(r) for r in rows]


def get_related(repo_id: str, node_id: str, edge_type: str, direction: str) -> list[dict]:
    conn = get_connection()
    if direction == "out":
        rows = conn.execute(
            "SELECT target FROM edges WHERE repo_id = ? AND source = ? AND type = ?",
            (repo_id, node_id, edge_type),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT source FROM edges WHERE repo_id = ? AND target = ? AND type = ?",
            (repo_id, node_id, edge_type),
        ).fetchall()
    conn.close()
    return get_nodes_by_ids(repo_id, [r[0] for r in rows])


def blast_radius(repo_id: str, node_id: str, depth: int) -> list[dict]:
    """Nodes that transitively depend on node_id (its callers/importers), up to `depth` hops."""
    conn = get_connection()
    rows = conn.execute("SELECT source, target FROM edges WHERE repo_id = ?", (repo_id,)).fetchall()
    conn.close()

    reverse_adj: dict[str, list[str]] = {}
    for source, target in rows:
        reverse_adj.setdefault(target, []).append(source)

    visited = {node_id}
    frontier = [node_id]
    for _ in range(depth):
        next_frontier = []
        for n in frontier:
            for pred in reverse_adj.get(n, []):
                if pred not in visited:
                    visited.add(pred)
                    next_frontier.append(pred)
        frontier = next_frontier
        if not frontier:
            break

    visited.discard(node_id)
    return get_nodes_by_ids(repo_id, list(visited))
