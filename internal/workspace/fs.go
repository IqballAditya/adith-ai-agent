package workspace

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
)

// FileNode represents a node (file or directory) in the workspace file tree.
type FileNode struct {
	Name     string     `json:"name"`
	Path     string     `json:"path"`
	IsDir    bool       `json:"is_dir"`
	Size     int64      `json:"size"`
	Children []FileNode `json:"children,omitempty"`
}

// isIgnored checks if a directory or file name matches the ignored list.
func isIgnored(name string) bool {
	switch name {
	case ".git", "node_modules", "venv", ".venv", "__pycache__", "dist":
		return true
	default:
		return false
	}
}

// ListFileTree recursively walks workspace root, filtering out .git, node_modules,
// venv, .venv, __pycache__, and dist.
func ListFileTree(root string) ([]FileNode, error) {
	cleanRoot := filepath.Clean(root)
	info, err := os.Stat(cleanRoot)
	if err != nil {
		return nil, fmt.Errorf("failed to stat workspace root: %w", err)
	}
	if !info.IsDir() {
		return nil, fmt.Errorf("workspace root is not a directory: %s", cleanRoot)
	}

	return walkDir(cleanRoot, "")
}

func walkDir(baseDir, relDir string) ([]FileNode, error) {
	currentDir := filepath.Join(baseDir, relDir)
	entries, err := os.ReadDir(currentDir)
	if err != nil {
		return nil, fmt.Errorf("failed to read directory %s: %w", currentDir, err)
	}

	nodes := make([]FileNode, 0, len(entries))

	for _, entry := range entries {
		name := entry.Name()
		if isIgnored(name) {
			continue
		}

		relPath := filepath.ToSlash(filepath.Join(relDir, name))
		isDir := entry.IsDir()

		node := FileNode{
			Name:  name,
			Path:  relPath,
			IsDir: isDir,
		}

		if isDir {
			children, err := walkDir(baseDir, filepath.Join(relDir, name))
			if err != nil {
				return nil, err
			}
			if children == nil {
				node.Children = []FileNode{}
			} else {
				node.Children = children
			}
		} else {
			info, err := entry.Info()
			if err != nil {
				return nil, fmt.Errorf("failed to get file info for %s: %w", relPath, err)
			}
			node.Size = info.Size()
		}

		nodes = append(nodes, node)
	}

	// Sort directories first, then alphabetical by name
	sort.Slice(nodes, func(i, j int) bool {
		if nodes[i].IsDir != nodes[j].IsDir {
			return nodes[i].IsDir
		}
		return nodes[i].Name < nodes[j].Name
	})

	return nodes, nil
}
