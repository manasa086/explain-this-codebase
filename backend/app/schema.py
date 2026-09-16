import strawberry

from app.db import save_graph
from app.graph_builder import build_graph, graph_stats
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
class Repo:
    id: str
    url: str
    status: str
    files: list[FileNode]
    stats: RepoStats


@strawberry.type
class Query:
    @strawberry.field
    def health(self) -> str:
        return "ok"


@strawberry.type
class Mutation:
    @strawberry.mutation
    def analyze_repo(self, url: str) -> Repo:
        local_path = clone_repo(url)
        files = [FileNode(path=p) for p in list_files(local_path)]

        graph = build_graph(local_path)
        repo_id = repo_slug(url)
        save_graph(repo_id, url, graph)
        stats = graph_stats(graph)

        return Repo(
            id=repo_id,
            url=url,
            status="analyzed",
            files=files,
            stats=RepoStats(
                num_nodes=stats["num_nodes"],
                num_edges=stats["num_edges"],
                num_files=stats["num_files"],
                num_functions=stats["num_functions"],
                num_classes=stats["num_classes"],
            ),
        )


schema = strawberry.Schema(query=Query, mutation=Mutation)
