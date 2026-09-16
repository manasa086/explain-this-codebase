# Explain This Codebase

An AI-powered tool that clones a codebase, parses it into a dependency/call graph, and lets you explore it visually with LLM-generated summaries per module.

## Stack
- **Backend:** Python, FastAPI, Strawberry GraphQL, GitPython
- **Frontend:** React, TypeScript, Apollo Client, react-flow (coming in a later phase)

## Status
Phase 1 (backend skeleton) complete: `analyzeRepo` mutation clones a repo and lists its files via GraphQL. No AST parsing / graph building yet — that's Phase 2.

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
    url
    status
    files {
      path
    }
  }
}
```
