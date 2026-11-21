package workspace_test

import (
	"errors"
	"os"
	"path/filepath"
	"testing"

	"adith-ai-studio/internal/workspace"
)

func TestApplyDiff_ExistingFileSuccess(t *testing.T) {
	tmpDir := t.TempDir()
	filePath := filepath.Join(tmpDir, "hello.txt")
	if err := os.WriteFile(filePath, []byte("Hello, World!\n"), 0644); err != nil {
		t.Fatal(err)
	}

	err := workspace.ApplyDiff(tmpDir, "hello.txt", "Hello, World!\n", "Hello, ADITH AI STUDIO!\n")
	if err != nil {
		t.Fatalf("ApplyDiff failed: %v", err)
	}

	content, err := os.ReadFile(filePath)
	if err != nil {
		t.Fatal(err)
	}
	if string(content) != "Hello, ADITH AI STUDIO!\n" {
		t.Errorf("unexpected content: %q", string(content))
	}
}

func TestApplyDiff_NewFileCreation(t *testing.T) {
	tmpDir := t.TempDir()
	relPath := filepath.Join("subdir", "nested", "newfile.go")

	err := workspace.ApplyDiff(tmpDir, relPath, "", "package nested\n")
	if err != nil {
		t.Fatalf("ApplyDiff failed creating new file: %v", err)
	}

	fullPath := filepath.Join(tmpDir, relPath)
	content, err := os.ReadFile(fullPath)
	if err != nil {
		t.Fatalf("expected file to exist: %v", err)
	}
	if string(content) != "package nested\n" {
		t.Errorf("unexpected content: %q", string(content))
	}
}

func TestApplyDiff_ContentMismatch(t *testing.T) {
	tmpDir := t.TempDir()
	filePath := filepath.Join(tmpDir, "data.txt")
	originalOnDisk := "line 1\nline 2 on disk\n"
	if err := os.WriteFile(filePath, []byte(originalOnDisk), 0644); err != nil {
		t.Fatal(err)
	}

	expectedOriginal := "line 1\nline 2 expected\n"
	newContent := "line 1\nline 2 modified\n"

	err := workspace.ApplyDiff(tmpDir, "data.txt", expectedOriginal, newContent)
	if err == nil {
		t.Fatal("expected content mismatch error, got nil")
	}

	if !errors.Is(err, workspace.ErrContentMismatch) {
		t.Errorf("expected ErrContentMismatch, got %v", err)
	}

	// Verify file is unchanged on disk
	content, err := os.ReadFile(filePath)
	if err != nil {
		t.Fatal(err)
	}
	if string(content) != originalOnDisk {
		t.Errorf("file on disk was modified despite error! Got %q", string(content))
	}
}

func TestApplyDiff_PathTraversalEscapesRoot(t *testing.T) {
	tmpDir := t.TempDir()
	err := workspace.ApplyDiff(tmpDir, "../escape.txt", "", "malicious")
	if err == nil {
		t.Fatal("expected path traversal error, got nil")
	}
	if !errors.Is(err, workspace.ErrPathEscapesRoot) {
		t.Errorf("expected ErrPathEscapesRoot, got %v", err)
	}
}

func TestApplyDiff_NonExistentWithNonEmptyOriginal(t *testing.T) {
	tmpDir := t.TempDir()
	err := workspace.ApplyDiff(tmpDir, "missing.txt", "expected something", "new content")
	if err == nil {
		t.Fatal("expected error when file does not exist but original is specified, got nil")
	}
	if !errors.Is(err, workspace.ErrContentMismatch) {
		t.Errorf("expected ErrContentMismatch, got %v", err)
	}
}
