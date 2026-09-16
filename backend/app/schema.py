import strawberry

from app.repo_service import clone_repo, list_files


@strawberry.type
class FileNode:
    path: str


@strawberry.type
class Repo:
    url: str
    status: str
    files: list[FileNode]


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
        return Repo(url=url, status="cloned", files=files)


schema = strawberry.Schema(query=Query, mutation=Mutation)
