from __future__ import annotations

import os
from typing import Optional

from agent.memory.vector_store import VectorStore
from agent.parser import ASTParser


_EXT_TO_LANG = {
    ".py": "python",
    ".go": "go",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
}

_IGNORED_DIRS = {
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".env",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",
    "vendor",
    ".idea",
    ".vscode",
}


class CodebaseIndexer:
    def __init__(self, vector_store: Optional[VectorStore] = None) -> None:
        self.vector_store = vector_store or VectorStore()

    def index_workspace(self, workspace_root: str, workspace_id: str) -> dict:
        if not os.path.isdir(workspace_root):
            return {
                "workspace_id": workspace_id,
                "files_indexed": 0,
                "symbols_indexed": 0,
                "status": "error",
                "error": f"Path '{workspace_root}' is not a valid directory",
            }

        files_indexed = 0
        symbols_indexed = 0

        for root, dirs, files in os.walk(workspace_root):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in _IGNORED_DIRS and not d.startswith(".")]

            for file_name in files:
                _, ext = os.path.splitext(file_name)
                lang = _EXT_TO_LANG.get(ext.lower())
                if not lang:
                    continue

                full_path = os.path.join(root, file_name)
                rel_path = os.path.relpath(full_path, workspace_root).replace("\\", "/")

                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        code = f.read()
                except Exception:
                    continue

                symbols = ASTParser.parse_code(code, lang)
                if symbols:
                    count = self.vector_store.index_symbols(
                        workspace_id=workspace_id,
                        symbols=symbols,
                        file_path=rel_path,
                    )
                    symbols_indexed += count
                    files_indexed += 1

        return {
            "workspace_id": workspace_id,
            "files_indexed": files_indexed,
            "symbols_indexed": symbols_indexed,
            "status": "success",
        }
