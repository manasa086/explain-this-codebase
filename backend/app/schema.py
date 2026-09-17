import asyncio
from typing import AsyncGenerator

import strawberry

from app.db import (
    blast_radius as db_blast_radius,
    get_files,
    get_node as db_get_node,
    get_related,
    get_repo,
    get_stats,
    save_files,
    save_graph,
    search_nodes as db_search_nodes,
)
from app.graph_builder import build_graph
from app.progress import ProgressEvent, broker
from app.repo_service import clone_repo, list_files, repo_slug


@strawberry.type
class FileNode:
    path: str


@strawberry.type
class RepoStats:
    num_nodes: int
    num_edges: int
    num_files: int
    num_functions: int
    num_classes: int


@strawberry.type
class Node:
    id: str
    node_type: str
    name: str
    path: str | None
    start_line: int | None
    end_line: int | None
    repo_id: strawberry.Private[str]

    @strawberry.field
    def calls(self) -> list["Node"]:
        return _to_nodes(get_related(self.repo_id, self.id, "CALLS", "out"), self.repo_id)

    @strawberry.field
    def called_by(self) -> list["Node"]:
        return _to_nodes(get_related(self.repo_id, self.id, "CALLS", "in"), self.repo_id)

    @strawberry.field
    def imports(self) -> list["Node"]:
        return _to_nodes(get_related(self.repo_id, self.id, "IMPORTS", "out"), self.repo_id)

    @strawberry.field
    def imported_by(self) -> list["Node"]:
        return _to_nodes(get_related(self.repo_id, self.id, "IMPORTS", "in"), self.repo_id)

    @strawberry.field
    def defines(self) -> list["Node"]:
        return _to_nodes(get_related(self.repo_id, self.id, "DEFINES", "out"), self.repo_id)

    @strawberry.field
    def inherits_from(self) -> list["Node"]:
        return _to_nodes(get_related(self.repo_id, self.id, "INHERITS", "out"), self.repo_id)

    @strawberry.field
    def blast_radius(self, depth: int = 2) -> list["Node"]:
        return _to_nodes(db_blast_radius(self.repo_id, self.id, depth), self.repo_id)


def _to_node(data: dict, repo_id: str) -> Node:
    return Node(
        id=data["id"],
        node_type=data["node_type"],
        name=data["name"],
        path=data["path"],
        start_line=data["start_line"],
        end_line=data["end_line"],
        repo_id=repo_id,
    )


def _to_nodes(rows: list[dict], repo_id: str) -> list[Node]:
    return [_to_node(r, repo_id) for r in rows]


@strawberry.type
class Repo:
    id: str
    url: str
    status: str
    analyzed_at: str
    files: list[FileNode]
    stats: RepoStats


def _build_repo(repo_id: str) -> Repo | None:
    row = get_repo(repo_id)
    if not row:
        return None
    return Repo(
        id=row["id"],
        url=row["url"],
        status="analyzed",
        analyzed_at=row["analyzed_at"],
        files=[FileNode(path=p) for p in get_files(repo_id)],
        stats=RepoStats(**get_stats(repo_id)),
    )


@strawberry.type
class Query:
    @strawberry.field
    def health(self) -> str:
        return "ok"

    @strawberry.field
    def repo(self, id: str) -> Repo | None:
        return _build_repo(id)

    @strawberry.field
    def node(self, repo_id: str, node_id: str) -> Node | None:
        row = db_get_node(repo_id, node_id)
        return _to_node(row, repo_id) if row else None

    @strawberry.field
    def search_nodes(self, repo_id: str, query: str, limit: int = 50) -> list[Node]:
        return _to_nodes(db_search_nodes(repo_id, query, limit), repo_id)

    @strawberry.field
    def blast_radius(self, repo_id: str, node_id: str, depth: int = 2) -> list[Node]:
        return _to_nodes(db_blast_radius(repo_id, node_id, depth), repo_id)


@strawberry.type
class AnalysisStarted:
    repo_id: str
    status: str


async def _run_analysis(url: str, repo_id: str) -> None:
    try:
        await broker.publish(repo_id, ProgressEvent(stage="cloning", message=f"Cloning {url}"))
        local_path = await asyncio.to_thread(clone_repo, url)

        await broker.publish(repo_id, ProgressEvent(stage="parsing", message="Parsing files and building graph"))
        graph = await asyncio.to_thread(build_graph, local_path)
        files = await asyncio.to_thread(list_files, local_path)

        await broker.publish(repo_id, ProgressEvent(stage="saving", message="Persisting graph to storage"))
        await asyncio.to_thread(save_graph, repo_id, url, graph)
        await asyncio.to_thread(save_files, repo_id, files)

        await broker.publish(repo_id, ProgressEvent(stage="done", message="Analysis complete"))
    except Exception as exc:
        await broker.publish(repo_id, ProgressEvent(stage="error", message=str(exc)))


@strawberry.type
class Mutation:
    @strawberry.mutation
    def analyze_repo(self, url: str) -> AnalysisStarted:
        repo_id = repo_slug(url)
        asyncio.create_task(_run_analysis(url, repo_id))
        return AnalysisStarted(repo_id=repo_id, status="started")


@strawberry.type
class AnalysisProgress:
    repo_id: str
    stage: str
    message: str


@strawberry.type
class Subscription:
    @strawberry.subscription
    async def analysis_progress(self, repo_id: str) -> AsyncGenerator[AnalysisProgress, None]:
        queue = broker.subscribe(repo_id)
        try:
            while True:
                event = await queue.get()
                yield AnalysisProgress(repo_id=repo_id, stage=event.stage, message=event.message)
                if event.stage in ("done", "error"):
                    break
        finally:
            broker.unsubscribe(repo_id, queue)


schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)
