# Explain This Codebase

An AI-powered tool that clones a codebase, parses it into a dependency/call graph, and lets you explore it visually with LLM-generated summaries per module.

## Stack
- **Backend:** Python, FastAPI, Strawberry GraphQL, GitPython, networkx, SQLite
- **Frontend:** React, TypeScript, Vite, Apollo Client, @xyflow/react (graph visualization)

## Status
- Phase 1: backend skeleton — `analyzeRepo` mutation clones a repo and lists its files via GraphQL. Done.
- Phase 2: static analysis engine — AST parsing (imports, functions, classes, calls), a networkx dependency/call graph with cross-file resolution, and SQLite persistence. Done.
- Phase 3: full GraphQL API over the persisted graph — `repo(id)`, `node(repoId, nodeId)` with relationship fields (`calls`, `calledBy`, `imports`, `importedBy`, `defines`, `inheritsFrom`), `searchNodes`, and `blastRadius` (reverse-dependency BFS to N hops). Done.
- Phase 4: progress streaming — `analyzeRepo` now kicks off cloning/parsing/saving in the background and returns immediately with a `repoId`; an `analysisProgress(repoId)` GraphQL subscription streams `cloning → parsing → saving → done` over WebSocket. Done.
- Phase 5: React frontend shell — repo URL input, Apollo Client (split HTTP/WebSocket link), live progress log wired to the subscription, and graph stats displayed once analysis completes. Done.
- Phase 6: interactive graph visualization — a new `graph(repoId)` query returns the full node/edge set, rendered with @xyflow/react. Starts collapsed at file level (with function-level `CALLS`/`INHERITS` edges aggregated up to their containing files); clicking a file expands it to show its functions/classes; clicking a function/class opens a detail panel with its `calls`/`calledBy`. Done.
- Phase 7 (next): LLM-based summarization layer (per-file/function plain-English summaries, content-hash cached).

## Running locally

**Backend:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
GraphQL playground: `http://127.0.0.1:8000/graphql`

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```
Opens at `http://localhost:5173`.

## Example GraphQL operations

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

Once done, fetch the graph stats:
```graphql
query {
  repo(id: "<repoId>") {
    url
    analyzedAt
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
