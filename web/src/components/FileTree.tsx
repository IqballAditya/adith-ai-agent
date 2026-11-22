import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  FileText,
  FileCode,
  FileJson,
  RefreshCw,
  Search,
  Database,
} from 'lucide-react'
import { FileNode } from '../types'

interface FileTreeProps {
  activePath?: string
  onSelectFile: (path: string) => void
}

const getFileIcon = (name: string) => {
  const ext = name.split('.').pop()?.toLowerCase()
  switch (ext) {
    case 'go':
      return <FileCode className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />
    case 'py':
      return <FileCode className="w-3.5 h-3.5 text-yellow-400 flex-shrink-0" />
    case 'ts':
    case 'tsx':
      return <FileCode className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
    case 'js':
    case 'jsx':
    case 'mjs':
      return <FileCode className="w-3.5 h-3.5 text-amber-300 flex-shrink-0" />
    case 'json':
      return <FileJson className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
    case 'sql':
      return <Database className="w-3.5 h-3.5 text-violet-400 flex-shrink-0" />
    case 'md':
    case 'txt':
      return <FileText className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
    default:
      return <FileText className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
  }
}

interface TreeNodeProps {
  node: FileNode
  level: number
  activePath?: string
  expandedDirs: Set<string>
  toggleDir: (path: string) => void
  onSelectFile: (path: string) => void
  filterQuery: string
}

const TreeNode: React.FC<TreeNodeProps> = ({
  node,
  level,
  activePath,
  expandedDirs,
  toggleDir,
  onSelectFile,
  filterQuery,
}) => {
  const isExpanded = expandedDirs.has(node.path)
  const isSelected = activePath === node.path

  // Filter check
  const matchesFilter = (n: FileNode): boolean => {
    if (!filterQuery) return true
    if (n.name.toLowerCase().includes(filterQuery.toLowerCase())) return true
    if (n.children) {
      return n.children.some(matchesFilter)
    }
    return false
  }

  if (filterQuery && !matchesFilter(node)) {
    return null
  }

  if (node.is_dir) {
    return (
      <div>
        <div
          onClick={() => toggleDir(node.path)}
          style={{ paddingLeft: `${level * 12 + 8}px` }}
          className="flex items-center gap-1.5 py-1 pr-2 hover:bg-studio-surface/80 rounded cursor-pointer text-slate-400 hover:text-slate-200 text-xs transition select-none group"
        >
          {isExpanded ? (
            <ChevronDown className="w-3 h-3 text-slate-500 group-hover:text-slate-300 flex-shrink-0" />
          ) : (
            <ChevronRight className="w-3 h-3 text-slate-500 group-hover:text-slate-300 flex-shrink-0" />
          )}
          {isExpanded ? (
            <FolderOpen className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
          ) : (
            <Folder className="w-3.5 h-3.5 text-indigo-400/80 flex-shrink-0" />
          )}
          <span className="truncate font-mono text-[11px] group-hover:text-white">
            {node.name}
          </span>
        </div>

        {isExpanded && node.children && (
          <div>
            {node.children.map((child) => (
              <TreeNode
                key={child.path}
                node={child}
                level={level + 1}
                activePath={activePath}
                expandedDirs={expandedDirs}
                toggleDir={toggleDir}
                onSelectFile={onSelectFile}
                filterQuery={filterQuery}
              />
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div
      onClick={() => onSelectFile(node.path)}
      style={{ paddingLeft: `${level * 12 + 20}px` }}
      className={`flex items-center gap-1.5 py-1 pr-2 rounded cursor-pointer text-xs transition select-none ${
        isSelected
          ? 'bg-studio-active text-indigo-300 font-medium'
          : 'text-slate-400 hover:text-slate-200 hover:bg-studio-surface/60'
      }`}
    >
      {getFileIcon(node.name)}
      <span className="truncate font-mono text-[11px]">{node.name}</span>
    </div>
  )
}

export const FileTree: React.FC<FileTreeProps> = ({ activePath, onSelectFile }) => {
  const [treeData, setTreeData] = useState<FileNode[]>([])
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set())
  const [filterQuery, setFilterQuery] = useState<string>('')

  const fetchTree = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/tree')
      if (!res.ok) {
        throw new Error(`Failed to fetch file tree (HTTP ${res.status})`)
      }
      const data: FileNode[] = await res.json()
      setTreeData(data || [])

      // Auto-expand top level directories
      const initialExpanded = new Set<string>()
      data.forEach((node) => {
        if (node.is_dir) {
          initialExpanded.add(node.path)
        }
      })
      setExpandedDirs((prev) => (prev.size === 0 ? initialExpanded : prev))
    } catch (err: any) {
      setError(err.message || 'Unknown error fetching file tree')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTree()
  }, [fetchTree])

  const toggleDir = (path: string) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
      }
      return next
    })
  }

  return (
    <div className="flex flex-col h-full bg-studio-card select-none border-r border-studio-border">
      {/* Header */}
      <div className="h-10 border-b border-studio-border px-3 flex items-center justify-between text-xs">
        <span className="font-semibold text-slate-200 tracking-wide uppercase text-[11px]">
          Explorer
        </span>
        <button
          onClick={fetchTree}
          title="Refresh tree"
          className="text-slate-400 hover:text-white p-1 rounded hover:bg-studio-surface transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Search Input */}
      <div className="p-2 border-b border-studio-border">
        <div className="relative flex items-center">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2 pointer-events-none" />
          <input
            type="text"
            value={filterQuery}
            onChange={(e) => setFilterQuery(e.target.value)}
            placeholder="Search files..."
            className="w-full bg-studio-surface border border-studio-border rounded px-2 py-1 pl-7 text-[11px] text-slate-200 placeholder-slate-500 outline-none focus:border-indigo-500 transition"
          />
        </div>
      </div>

      {/* Tree Content */}
      <div className="flex-1 overflow-y-auto py-2 px-1">
        {loading && treeData.length === 0 ? (
          <div className="p-4 text-center text-xs text-slate-500 font-mono">
            Loading files...
          </div>
        ) : error ? (
          <div className="p-3 text-xs text-rose-400 bg-rose-500/10 rounded m-2">
            <p className="font-semibold">Failed to load tree:</p>
            <p className="text-[11px] mt-1">{error}</p>
            <button
              onClick={fetchTree}
              className="mt-2 text-[10px] text-indigo-400 underline hover:text-indigo-300"
            >
              Retry
            </button>
          </div>
        ) : treeData.length === 0 ? (
          <div className="p-4 text-center text-xs text-slate-500 font-mono">
            Workspace is empty
          </div>
        ) : (
          treeData.map((node) => (
            <TreeNode
              key={node.path}
              node={node}
              level={0}
              activePath={activePath}
              expandedDirs={expandedDirs}
              toggleDir={toggleDir}
              onSelectFile={onSelectFile}
              filterQuery={filterQuery}
            />
          ))
        )}
      </div>
    </div>
  )
}
