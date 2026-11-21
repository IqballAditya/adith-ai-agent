package workspace

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

var (
	// ErrContentMismatch is returned when the existing file does not match expected original content.
	ErrContentMismatch = errors.New("content mismatch: file has diverged from expected original")

	// ErrPathEscapesRoot is returned when the relative path attempts directory traversal outside root.
	ErrPathEscapesRoot = errors.New("invalid path: target escapes workspace root")

	// ErrFileLocked is returned when a file cannot be written or renamed due to an external lock.
	ErrFileLocked = errors.New("file is locked by another process")
)

// normalizeNewlines standardizes CRLF and LF for clean comparison across platforms.
func normalizeNewlines(s string) string {
	return strings.ReplaceAll(s, "\r\n", "\n")
}

// isFileLocked checks if an error indicates a Windows sharing or lock violation.
func isFileLocked(err error) bool {
	if err == nil {
		return false
	}
	if errors.Is(err, os.ErrPermission) {
		return true
	}
	msg := strings.ToLower(err.Error())
	return strings.Contains(msg, "being used by another process") ||
		strings.Contains(msg, "sharing violation") ||
		strings.Contains(msg, "lock violation") ||
		strings.Contains(msg, "access is denied")
}

// ApplyDiff safely validates that current file content matches original (or handles
// new file creation if original is empty), and atomically updates the file on disk to modified.
func ApplyDiff(root string, relativePath string, original string, modified string) error {
	cleanRoot := filepath.Clean(root)
	targetPath := filepath.Clean(filepath.Join(cleanRoot, relativePath))

	// Path traversal protection
	rel, err := filepath.Rel(cleanRoot, targetPath)
	if err != nil || strings.HasPrefix(rel, "..") || rel == ".." {
		return ErrPathEscapesRoot
	}

	parentDir := filepath.Dir(targetPath)
	var existingPerm os.FileMode = 0644

	// Read existing file content if it exists
	existingBytes, err := os.ReadFile(targetPath)
	if err != nil {
		if os.IsNotExist(err) {
			if original != "" {
				return fmt.Errorf("%w: file %s does not exist on disk", ErrContentMismatch, relativePath)
			}
		} else {
			if isFileLocked(err) {
				return fmt.Errorf("%w: cannot read file %s: %v", ErrFileLocked, relativePath, err)
			}
			return fmt.Errorf("failed to read file %s: %w", relativePath, err)
		}
	} else {
		// Existing file was read successfully
		if stat, statErr := os.Stat(targetPath); statErr == nil {
			existingPerm = stat.Mode().Perm()
		}

		if original == "" && len(existingBytes) > 0 {
			return fmt.Errorf("%w: expected new file but %s already exists and is not empty", ErrContentMismatch, relativePath)
		}

		if original != "" && normalizeNewlines(string(existingBytes)) != normalizeNewlines(original) {
			return fmt.Errorf("%w: content of %s has diverged from expected original", ErrContentMismatch, relativePath)
		}
	}

	// Ensure parent directory exists
	if err := os.MkdirAll(parentDir, 0755); err != nil {
		return fmt.Errorf("failed to create directory %s: %w", parentDir, err)
	}

	// Write atomically using temporary file in same directory
	tmpFile, err := os.CreateTemp(parentDir, ".diff-tmp-*")
	if err != nil {
		return fmt.Errorf("failed to create temporary file in %s: %w", parentDir, err)
	}
	tmpPath := tmpFile.Name()
	defer func() {
		if tmpPath != "" {
			_ = os.Remove(tmpPath)
		}
	}()

	if _, err := tmpFile.WriteString(modified); err != nil {
		_ = tmpFile.Close()
		return fmt.Errorf("failed to write to temporary file: %w", err)
	}
	if err := tmpFile.Sync(); err != nil {
		_ = tmpFile.Close()
		return fmt.Errorf("failed to sync temporary file: %w", err)
	}
	if err := tmpFile.Close(); err != nil {
		return fmt.Errorf("failed to close temporary file: %w", err)
	}

	_ = os.Chmod(tmpPath, existingPerm)

	// Atomically replace target file
	if err := os.Rename(tmpPath, targetPath); err != nil {
		if isFileLocked(err) {
			return fmt.Errorf("%w: file %s is locked, please close it and retry", ErrFileLocked, relativePath)
		}
		return fmt.Errorf("failed to atomically update file %s: %w", relativePath, err)
	}

	// Rename succeeded; disarm defer cleanup
	tmpPath = ""
	return nil
}
