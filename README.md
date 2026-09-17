# Explain This Codebase

An AI-powered tool that clones a codebase, parses it into a dependency/call graph, and lets you explore it visually with LLM-generated summaries per module.

## Stack
- **Backend:** Python, FastAPI, Strawberry GraphQL, GitPython
- **Frontend:** React, TypeScript, Apollo Client, react-flow (coming in a later phase)

## Status
- Phase 1: backend skeleton — `analyzeRepo` mutation clones a repo and lists its files via GraphQL. Done.
- Phase 2: static analysis engine — AST parsing (imports, functions, classes, calls), a networkx dependency/call graph with cross-file resolution, and SQLite persistence. `analyzeRepo` now also returns graph stats. Done.
- Phase 3: full GraphQL API over the persisted graph — `repo(id)`, `node(repoId, nodeId)` with relationship fields (`calls`, `calledBy`, `imports`, `importedBy`, `defines`, `inheritsFrom`), `searchNodes`, and `blastRadius` (reverse-dependency BFS to N hops). Done.
- Phase 4: progress streaming — `analyzeRepo` now kicks off cloning/parsing/saving in the background (via `asyncio.to_thread`, so it doesn't block the event loop) and returns immediately with a `repoId`; a `analysisProgress(repoId)` GraphQL subscription streams `cloning → parsing → saving → done` over WebSocket. A late subscriber gets the current state replayed instead of hanging. Done.
- Phase 5 (next): React frontend shell (repo input, progress bar wired to the subscription, Apollo Client).

## Example queries

Start an analysis (returns immediately) and watch it progress:
```graphql
mutation {
  analyzeRepo(url: "https://github.com/octocat/Hello-World.git") {
    repoId
    status
  }
}

subscription {
  analysisProgress(repoId: "<repoId from above>") {
    stage
    message
  }
}
```

Search for a node, then inspect its relationships:
```graphql
query {
  searchNodes(repoId: "<repoId>", query: "clone_repo") {
    id
    nodeType
    name
    path
  }
}

query {
  node(repoId: "<repoId>", nodeId: "function:backend/app/repo_service.py::clone_repo") {
    name
    calls { name }
    calledBy { name path }
  }
}

query {
  blastRadius(repoId: "<repoId>", nodeId: "function:backend/app/repo_service.py::repo_slug", depth: 2) {
    name
    path
  }
}
```

## Running locally
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

GraphQL playground: `http://127.0.0.1:8000/graphql`

Example mutation:
```graphql
mutation {
  analyzeRepo(url: "https://github.com/octocat/Hello-World.git") {
    id
    url
    status
    files {
      path
    }
    stats {
      numNodes
      numEdges
      numFiles
      numFunctions
      numClasses
    }
  }
}
```
