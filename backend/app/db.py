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
