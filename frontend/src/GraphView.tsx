import { useCallback, useMemo, useState } from 'react'
import { gql } from '@apollo/client'
import { useLazyQuery, useQuery } from '@apollo/client/react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node as FlowNode,
  type Edge as FlowEdge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import './GraphView.css'

const GRAPH_QUERY = gql`
  query Graph($repoId: String!) {
    graph(repoId: $repoId) {
      nodes {
        id
        nodeType
        name
        path
      }
      edges {
        source
        target
        edgeType
      }
    }
  }
`

const NODE_DETAIL_QUERY = gql`
  query NodeDetail($repoId: String!, $nodeId: String!) {
    node(repoId: $repoId, nodeId: $nodeId) {
      id
      name
      nodeType
      path
      startLine
      endLine
      calls {
        id
        name
      }
      calledBy {
        id
        name
      }
    }
  }
`

type GNode = { id: string; nodeType: string; name: string; path: string | null }
type GEdge = { source: string; target: string; edgeType: string }

const NODE_COLORS: Record<string, string> = {
  File: '#2563eb',
  Function: '#16a34a',
  Class: '#d97706',
}

const EDGE_COLORS: Record<string, string> = {
  IMPORTS: '#94a3b8',
  CALLS: '#16a34a',
  DEFINES: '#cbd5e1',
  INHERITS: '#d97706',
}

function layout(nodes: GNode[], edges: GEdge[], expanded: Set<string>) {
  const fileNodes = nodes.filter((n) => n.nodeType === 'File')
  const nodeById = new Map(nodes.map((n) => [n.id, n]))

  const containerOf = new Map<string, string>()
  edges.forEach((e) => {
    if (e.edgeType === 'DEFINES') containerOf.set(e.target, e.source)
  })

  const visibleIds = new Set<string>(fileNodes.map((n) => n.id))
  expanded.forEach((fileId) => {
    edges.forEach((e) => {
      if (e.edgeType === 'DEFINES' && e.source === fileId) visibleIds.add(e.target)
    })
  })

  const cols = Math.max(1, Math.ceil(Math.sqrt(fileNodes.length)))
  const spacingX = 260
  const spacingY = 180
  const filePositions = new Map<string, { x: number; y: number }>()

  const flowNodes: FlowNode[] = fileNodes.map((f, i) => {
    const col = i % cols
    const row = Math.floor(i / cols)
    const pos = { x: col * spacingX, y: row * spacingY }
    filePositions.set(f.id, pos)
    return {
      id: f.id,
      position: pos,
      data: { label: `${expanded.has(f.id) ? '📂' : '📁'} ${f.name}` },
      style: {
        background: NODE_COLORS.File,
        color: 'white',
        borderRadius: 6,
        padding: 8,
        fontSize: 12,
        cursor: 'pointer',
        border: expanded.has(f.id) ? '2px solid #1e3a8a' : '2px solid transparent',
      },
    }
  })

  expanded.forEach((fileId) => {
    const base = filePositions.get(fileId)
    if (!base) return
    const childIds = [...visibleIds].filter((id) => containerOf.get(id) === fileId)
    childIds.forEach((id, idx) => {
      const n = nodeById.get(id)
      if (!n) return
      flowNodes.push({
        id,
        position: { x: base.x + 70, y: base.y + 80 + idx * 46 },
        data: { label: n.name },
        style: {
          background: NODE_COLORS[n.nodeType] ?? '#999',
          color: 'white',
          borderRadius: 6,
          padding: 6,
          fontSize: 11,
          cursor: 'pointer',
        },
      })
    })
  })

  const flowEdges: FlowEdge[] = []
  const seen = new Set<string>()
  edges.forEach((e) => {
    let s = e.source
    let t = e.target
    if (!visibleIds.has(s)) s = containerOf.get(s) ?? s
    if (!visibleIds.has(t)) t = containerOf.get(t) ?? t
    if (!visibleIds.has(s) || !visibleIds.has(t) || s === t) return

    const key = `${s}->${t}:${e.edgeType}`
    if (seen.has(key)) return
    seen.add(key)
    flowEdges.push({
      id: key,
      source: s,
      target: t,
      label: e.edgeType,
      animated: e.edgeType === 'CALLS',
      style: { stroke: EDGE_COLORS[e.edgeType] ?? '#999' },
      labelStyle: { fontSize: 9, fill: '#666' },
    })
  })

  return { flowNodes, flowEdges }
}

export function GraphView({ repoId }: { repoId: string }) {
  const { data, loading, error } = useQuery(GRAPH_QUERY, { variables: { repoId } })
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [fetchDetail, { data: detailData }] = useLazyQuery(NODE_DETAIL_QUERY)

  const nodes: GNode[] = data?.graph?.nodes ?? []
  const edges: GEdge[] = data?.graph?.edges ?? []

  const { flowNodes, flowEdges } = useMemo(
    () => layout(nodes, edges, expanded),
    [nodes, edges, expanded],
  )

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: FlowNode) => {
      const gnode = nodes.find((n) => n.id === node.id)
      if (!gnode) return
      if (gnode.nodeType === 'File') {
        setExpanded((prev) => {
          const next = new Set(prev)
          if (next.has(node.id)) next.delete(node.id)
          else next.add(node.id)
          return next
        })
      } else {
        setSelectedId(node.id)
        fetchDetail({ variables: { repoId, nodeId: node.id } })
      }
    },
    [nodes, repoId, fetchDetail],
  )

  if (loading) return <p>Loading graph…</p>
  if (error) return <p className="error">{error.message}</p>

  const detail = detailData?.node

  return (
    <div className="graph-panel">
      <h3>Dependency graph</h3>
      <p className="hint">
        Click a file to expand/collapse it. Click a function or class to
        inspect its relationships.
      </p>
      <div className="graph-canvas">
        <ReactFlow nodes={flowNodes} edges={flowEdges} onNodeClick={onNodeClick} fitView>
          <Background />
          <Controls />
          <MiniMap />
        </ReactFlow>
      </div>
      {selectedId && detail && (
        <div className="node-detail">
          <h4>
            {detail.name} <span className="node-type">({detail.nodeType})</span>
          </h4>
          <p className="path">
            {detail.path}
            {detail.startLine ? `:${detail.startLine}-${detail.endLine}` : ''}
          </p>
          <div className="detail-columns">
            <div>
              <strong>Calls</strong>
              <ul>
                {detail.calls.length ? (
                  detail.calls.map((c: GNode) => <li key={c.id}>{c.name}</li>)
                ) : (
                  <li className="muted">none</li>
                )}
              </ul>
            </div>
            <div>
              <strong>Called by</strong>
              <ul>
                {detail.calledBy.length ? (
                  detail.calledBy.map((c: GNode) => <li key={c.id}>{c.name}</li>)
                ) : (
                  <li className="muted">none</li>
                )}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
