package database_test

import (
	"path/filepath"
	"testing"

	"adith-ai-studio/internal/database"
)

func TestInitDBAndMigrate(t *testing.T) {
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "test.db")

	db, err := database.InitDB(dbPath)
	if err != nil {
		t.Fatalf("InitDB failed: %v", err)
	}
	defer db.Close()

	// Verify journal_mode is WAL
	var journalMode string
	err = db.QueryRow("PRAGMA journal_mode;").Scan(&journalMode)
	if err != nil {
		t.Fatalf("Failed to query journal_mode: %v", err)
	}
	if journalMode != "wal" {
		t.Errorf("Expected journal_mode 'wal', got '%s'", journalMode)
	}

	// Verify busy_timeout is set (at least 5000)
	var busyTimeout int
	err = db.QueryRow("PRAGMA busy_timeout;").Scan(&busyTimeout)
	if err != nil {
		t.Fatalf("Failed to query busy_timeout: %v", err)
	}
	if busyTimeout < 5000 {
		t.Errorf("Expected busy_timeout >= 5000, got %d", busyTimeout)
	}

	// Run migration
	if err := database.Migrate(db); err != nil {
		t.Fatalf("Migrate failed: %v", err)
	}

	// Verify required tables exist
	expectedTables := []string{
		"workspaces",
		"chat_threads",
		"messages",
		"tool_executions",
		"codebase_files",
	}

	for _, table := range expectedTables {
		var name string
		err := db.QueryRow("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", table).Scan(&name)
		if err != nil {
			t.Errorf("Expected table %q to exist, but got error: %v", table, err)
		}
		if name != table {
			t.Errorf("Expected table name %q, got %q", table, name)
		}
	}

	// Verify idempotent migrations (running migrate again should not fail)
	if err := database.Migrate(db); err != nil {
		t.Fatalf("Second Migrate call (idempotency check) failed: %v", err)
	}
}
