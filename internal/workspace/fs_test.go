package workspace_test

import (
	"os"
	"path/filepath"
	"testing"

	"adith-ai-studio/internal/workspace"
)

func TestListFileTree_Success(t *testing.T) {
	tmpDir := t.TempDir()

	// Create structure:
	// root/
	//   README.md
	//   src/
	//     main.go
	//     utils.go
	//   docs/
	//     arch.md
	if err := os.WriteFile(filepath.Join(tmpDir, "README.md"), []byte("# Test Project"), 0644); err != nil {
		t.Fatal(err)
	}
	srcDir := filepath.Join(tmpDir, "src")
	if err := os.MkdirAll(srcDir, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(srcDir, "main.go"), []byte("package main"), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(srcDir, "utils.go"), []byte("package main\nfunc util(){}"), 0644); err != nil {
		t.Fatal(err)
	}
	docsDir := filepath.Join(tmpDir, "docs")
	if err := os.MkdirAll(docsDir, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(docsDir, "arch.md"), []byte("# Architecture"), 0644); err != nil {
		t.Fatal(err)
	}

	nodes, err := workspace.ListFileTree(tmpDir)
	if err != nil {
		t.Fatalf("ListFileTree failed: %v", err)
	}

	if len(nodes) == 0 {
		t.Fatal("expected non-empty file tree")
	}

	// Verify top-level names
	nodeMap := make(map[string]workspace.FileNode)
	for _, n := range nodes {
		nodeMap[n.Name] = n
	}

	if _, ok := nodeMap["README.md"]; !ok {
		t.Error("expected README.md in root")
	}
	if n, ok := nodeMap["src"]; !ok || !n.IsDir {
		t.Error("expected src directory in root")
	} else {
		if len(n.Children) != 2 {
			t.Errorf("expected 2 children in src, got %d", len(n.Children))
		}
	}
	if n, ok := nodeMap["docs"]; !ok || !n.IsDir {
		t.Error("expected docs directory in root")
	} else {
		if len(n.Children) != 1 {
			t.Errorf("expected 1 child in docs, got %d", len(n.Children))
		}
	}
}

func TestListFileTree_IgnoreFilter(t *testing.T) {
	tmpDir := t.TempDir()

	// Ignored directories: .git, node_modules, venv, .venv, __pycache__, dist
	ignored := []string{".git", "node_modules", "venv", ".venv", "__pycache__", "dist"}
	for _, dir := range ignored {
		d := filepath.Join(tmpDir, dir)
		if err := os.MkdirAll(d, 0755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(d, "dummy.txt"), []byte("ignored"), 0644); err != nil {
			t.Fatal(err)
		}
	}

	// Allowed items
	validDir := filepath.Join(tmpDir, "pkg")
	if err := os.MkdirAll(validDir, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(validDir, "pkg.go"), []byte("package pkg"), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(tmpDir, "index.ts"), []byte("console.log('hi')"), 0644); err != nil {
		t.Fatal(err)
	}

	nodes, err := workspace.ListFileTree(tmpDir)
	if err != nil {
		t.Fatalf("ListFileTree failed: %v", err)
	}

	for _, n := range nodes {
		for _, ign := range ignored {
			if n.Name == ign {
				t.Errorf("node %s should have been filtered out", n.Name)
			}
		}
	}

	nodeMap := make(map[string]workspace.FileNode)
	for _, n := range nodes {
		nodeMap[n.Name] = n
	}
	if _, ok := nodeMap["pkg"]; !ok {
		t.Error("expected pkg in tree")
	}
	if _, ok := nodeMap["index.ts"]; !ok {
		t.Error("expected index.ts in tree")
	}
}

func TestListFileTree_InvalidPaths(t *testing.T) {
	_, err := workspace.ListFileTree(filepath.Join(t.TempDir(), "nonexistent"))
	if err == nil {
		t.Error("expected error for nonexistent path")
	}

	tmpFile := filepath.Join(t.TempDir(), "file.txt")
	if err := os.WriteFile(tmpFile, []byte("content"), 0644); err != nil {
		t.Fatal(err)
	}
	_, err = workspace.ListFileTree(tmpFile)
	if err == nil {
		t.Error("expected error when root is a file, not a directory")
	}
}
