# Explain This Codebase

An AI-powered tool that clones a codebase, parses it into a dependency/call graph, and lets you explore it visually with LLM-generated summaries per module.

## Stack
- **Backend:** Python, FastAPI, Strawberry GraphQL, GitPython
- **Frontend:** React, TypeScript, Apollo Client, react-flow (coming in a later phase)

## Status
- Phase 1: backend skeleton — `analyzeRepo` mutation clones a repo and lists its files via GraphQL. Done.
- Phase 2: static analysis engine — AST parsing (imports, functions, classes, calls), a networkx dependency/call graph with cross-file resolution, and SQLite persistence. `analyzeRepo` now also returns graph stats. Done.
- Phase 3 (next): full GraphQL API over the graph — per-node queries, search, blast-radius.

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
