import { useState } from 'react'
import { gql } from '@apollo/client'
import { useMutation, useSubscription, useLazyQuery } from '@apollo/client/react'
import './App.css'

const ANALYZE_REPO = gql`
  mutation AnalyzeRepo($url: String!) {
    analyzeRepo(url: $url) {
      repoId
      status
    }
  }
`

const ANALYSIS_PROGRESS = gql`
  subscription AnalysisProgress($repoId: String!) {
    analysisProgress(repoId: $repoId) {
      stage
      message
    }
  }
`

const REPO_QUERY = gql`
  query Repo($id: String!) {
    repo(id: $id) {
      url
      status
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
`

type ProgressEvent = { stage: string; message: string }

function App() {
  const [url, setUrl] = useState('https://github.com/octocat/Hello-World.git')
  const [repoId, setRepoId] = useState<string | null>(null)
  const [log, setLog] = useState<ProgressEvent[]>([])
  const [finished, setFinished] = useState(false)

  const [analyzeRepo, { loading: starting, error: mutationError }] =
    useMutation(ANALYZE_REPO)
  const [fetchRepo, { data: repoData }] = useLazyQuery(REPO_QUERY)

  useSubscription(ANALYSIS_PROGRESS, {
    variables: repoId ? { repoId } : undefined,
    skip: !repoId || finished,
    onData: ({ data }) => {
      const event = data.data?.analysisProgress
      if (!event) return
      setLog((prev) => [...prev, event])
      if (event.stage === 'done' || event.stage === 'error') {
        setFinished(true)
        if (event.stage === 'done' && repoId) {
          fetchRepo({ variables: { id: repoId } })
        }
      }
    },
  })

  const handleAnalyze = async () => {
    setLog([])
    setFinished(false)
    setRepoId(null)
    const result = await analyzeRepo({ variables: { url } })
    const newRepoId = result.data?.analyzeRepo?.repoId
    if (newRepoId) setRepoId(newRepoId)
  }

  const stats = repoData?.repo?.stats

  return (
    <div className="app">
      <h1>Explain This Codebase</h1>
      <p className="subtitle">
        Paste a public GitHub repo URL to parse it into a dependency/call
        graph.
      </p>

      <div className="input-row">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://github.com/owner/repo.git"
        />
        <button onClick={handleAnalyze} disabled={starting}>
          {starting ? 'Starting…' : 'Analyze'}
        </button>
      </div>

      {mutationError && <p className="error">{mutationError.message}</p>}

      {repoId && (
        <div className="panel">
          <h3>Progress</h3>
          <ul className="log">
            {log.map((e, i) => (
              <li key={i} className={`stage-${e.stage}`}>
                <strong>{e.stage}</strong> — {e.message}
              </li>
            ))}
            {!finished && <li className="pending">waiting…</li>}
          </ul>
        </div>
      )}

      {stats && (
        <div className="panel">
          <h3>Graph stats</h3>
          <div className="stats-grid">
            <div>
              <span className="stat-value">{stats.numFiles}</span>
              <span className="stat-label">files</span>
            </div>
            <div>
              <span className="stat-value">{stats.numFunctions}</span>
              <span className="stat-label">functions</span>
            </div>
            <div>
              <span className="stat-value">{stats.numClasses}</span>
              <span className="stat-label">classes</span>
            </div>
            <div>
              <span className="stat-value">{stats.numNodes}</span>
              <span className="stat-label">nodes</span>
            </div>
            <div>
              <span className="stat-value">{stats.numEdges}</span>
              <span className="stat-label">edges</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
