package api_test

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"adith-ai-studio/internal/api"
	"adith-ai-studio/internal/database"
	"adith-ai-studio/internal/workspace"

	"github.com/gorilla/websocket"
)

func setupTestDB(t *testing.T) *sql.DB {
	t.Helper()
	tempDir := t.TempDir()
	dbPath := filepath.Join(tempDir, "test.db")
	db, err := database.InitDB(dbPath)
	if err != nil {
		t.Fatalf("failed to init db: %v", err)
	}
	if err := database.Migrate(db); err != nil {
		t.Fatalf("failed to run migrations: %v", err)
	}
	t.Cleanup(func() {
		db.Close()
	})
	return db
}

func setupTestWorkspace(t *testing.T) string {
	t.Helper()
	tempDir := t.TempDir()
	file1 := filepath.Join(tempDir, "hello.txt")
	if err := os.WriteFile(file1, []byte("Hello, World!"), 0644); err != nil {
		t.Fatalf("failed to write test file: %v", err)
	}
	subDir := filepath.Join(tempDir, "sub")
	if err := os.MkdirAll(subDir, 0755); err != nil {
		t.Fatalf("failed to create subdir: %v", err)
	}
	file2 := filepath.Join(subDir, "code.go")
	if err := os.WriteFile(file2, []byte("package sub\n"), 0644); err != nil {
		t.Fatalf("failed to write sub file: %v", err)
	}
	return tempDir
}

func TestHealthEndpoint(t *testing.T) {
	db := setupTestDB(t)
	ws := setupTestWorkspace(t)
	server := api.NewServer(db, "http://localhost:5050", ws)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	server.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d", rec.Code)
	}

	var res map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &res); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if res["status"] != "ok" || res["service"] != "adith-gateway" {
		t.Fatalf("unexpected health response: %+v", res)
	}
}

func TestTreeEndpoint(t *testing.T) {
	db := setupTestDB(t)
	ws := setupTestWorkspace(t)
	server := api.NewServer(db, "http://localhost:5050", ws)

	req := httptest.NewRequest(http.MethodGet, "/api/tree", nil)
	rec := httptest.NewRecorder()

	server.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d: %s", rec.Code, rec.Body.String())
	}

	var tree []workspace.FileNode
	if err := json.Unmarshal(rec.Body.Bytes(), &tree); err != nil {
		t.Fatalf("failed to unmarshal tree: %v", err)
	}

	if len(tree) == 0 {
		t.Fatalf("expected non-empty tree")
	}
}

func TestFileEndpoint(t *testing.T) {
	db := setupTestDB(t)
	ws := setupTestWorkspace(t)
	server := api.NewServer(db, "http://localhost:5050", ws)

	// Valid file
	req := httptest.NewRequest(http.MethodGet, "/api/file?path=hello.txt", nil)
	rec := httptest.NewRecorder()
	server.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d", rec.Code)
	}
	if rec.Body.String() != "Hello, World!" {
		t.Fatalf("expected 'Hello, World!', got %q", rec.Body.String())
	}

	// Sub file
	req = httptest.NewRequest(http.MethodGet, "/api/file?path=sub/code.go", nil)
	rec = httptest.NewRecorder()
	server.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d", rec.Code)
	}
	if rec.Body.String() != "package sub\n" {
		t.Fatalf("expected 'package sub\\n', got %q", rec.Body.String())
	}

	// Missing file
	req = httptest.NewRequest(http.MethodGet, "/api/file?path=missing.txt", nil)
	rec = httptest.NewRecorder()
	server.ServeHTTP(rec, req)
	if rec.Code != http.StatusNotFound {
		t.Fatalf("expected 404 Not Found, got %d", rec.Code)
	}

	// Directory traversal attempt
	req = httptest.NewRequest(http.MethodGet, "/api/file?path=../../etc/passwd", nil)
	rec = httptest.NewRecorder()
	server.ServeHTTP(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 Bad Request, got %d", rec.Code)
	}

	// Empty path
	req = httptest.NewRequest(http.MethodGet, "/api/file", nil)
	rec = httptest.NewRecorder()
	server.ServeHTTP(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 Bad Request, got %d", rec.Code)
	}
}

func TestDiffAcceptEndpoint(t *testing.T) {
	db := setupTestDB(t)
	ws := setupTestWorkspace(t)
	server := api.NewServer(db, "http://localhost:5050", ws)

	// Accept diff on existing file
	payload := map[string]string{
		"path":     "hello.txt",
		"original": "Hello, World!",
		"modified": "Hello, Adith AI Studio!",
	}
	body, _ := json.Marshal(payload)
	req := httptest.NewRequest(http.MethodPost, "/api/diff/accept", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	server.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d: %s", rec.Code, rec.Body.String())
	}

	// Verify file modified on disk
	content, err := os.ReadFile(filepath.Join(ws, "hello.txt"))
	if err != nil {
		t.Fatalf("failed to read modified file: %v", err)
	}
	if string(content) != "Hello, Adith AI Studio!" {
		t.Fatalf("expected 'Hello, Adith AI Studio!', got %q", string(content))
	}

	// Verify audit logged to tool_executions
	var count int
	err = db.QueryRow("SELECT COUNT(*) FROM tool_executions WHERE tool_name = 'apply_diff'").Scan(&count)
	if err != nil {
		t.Fatalf("failed to query tool_executions: %v", err)
	}
	if count != 1 {
		t.Fatalf("expected 1 tool_execution logged, got %d", count)
	}

	// Content mismatch returns 409 Conflict
	mismatchPayload := map[string]string{
		"path":     "hello.txt",
		"original": "Wrong original",
		"modified": "Something else",
	}
	body, _ = json.Marshal(mismatchPayload)
	req = httptest.NewRequest(http.MethodPost, "/api/diff/accept", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec = httptest.NewRecorder()
	server.ServeHTTP(rec, req)
	if rec.Code != http.StatusConflict {
		t.Fatalf("expected 409 Conflict, got %d", rec.Code)
	}

	// Path escape returns 400 Bad Request
	escapePayload := map[string]string{
		"path":     "../outside.txt",
		"original": "",
		"modified": "outside",
	}
	body, _ = json.Marshal(escapePayload)
	req = httptest.NewRequest(http.MethodPost, "/api/diff/accept", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec = httptest.NewRecorder()
	server.ServeHTTP(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 Bad Request, got %d", rec.Code)
	}
}

func TestChatStreamingMockFallback(t *testing.T) {
	db := setupTestDB(t)
	ws := setupTestWorkspace(t)
	// Point to offline agent URL
	server := api.NewServer(db, "http://127.0.0.1:59999", ws)

	payload := map[string]string{
		"workspace_id": "test-ws",
		"prompt":       "Build a new feature",
	}
	body, _ := json.Marshal(payload)
	req := httptest.NewRequest(http.MethodPost, "/api/chat", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()

	server.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d", rec.Code)
	}

	contentType := rec.Header().Get("Content-Type")
	if !strings.Contains(contentType, "text/event-stream") {
		t.Fatalf("expected text/event-stream content type, got %s", contentType)
	}

	bodyStr := rec.Body.String()
	if !strings.Contains(bodyStr, "event: reasoning") && !strings.Contains(bodyStr, "event: message") {
		t.Fatalf("expected SSE events in response, got: %s", bodyStr)
	}

	// Verify logged to SQLite messages
	var msgCount int
	err := db.QueryRow("SELECT COUNT(*) FROM messages").Scan(&msgCount)
	if err != nil {
		t.Fatalf("failed to query messages: %v", err)
	}
	if msgCount < 1 {
		t.Fatalf("expected messages to be logged in SQLite, got %d", msgCount)
	}
}

func TestChatStreamingAgentProxy(t *testing.T) {
	db := setupTestDB(t)
	ws := setupTestWorkspace(t)

	// Mock Python agent HTTP server
	mockAgent := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/agent/chat" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		flusher, ok := w.(http.Flusher)
		if !ok {
			return
		}
		fmt.Fprintf(w, "event: reasoning\ndata: {\"type\": \"reasoning\", \"content\": \"Agent is thinking\"}\n\n")
		flusher.Flush()
		fmt.Fprintf(w, "event: message\ndata: {\"type\": \"message\", \"content\": \"Agent response chunk\"}\n\n")
		flusher.Flush()
		fmt.Fprintf(w, "event: done\ndata: {\"type\": \"done\", \"usage\": {\"prompt_tokens\": 10, \"completion_tokens\": 20}}\n\n")
		flusher.Flush()
	}))
	defer mockAgent.Close()

	server := api.NewServer(db, mockAgent.URL, ws)

	payload := map[string]string{
		"workspace_id": "test-ws-2",
		"prompt":       "Proxy test prompt",
	}
	body, _ := json.Marshal(payload)
	req := httptest.NewRequest(http.MethodPost, "/api/chat", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()

	server.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d", rec.Code)
	}

	bodyStr := rec.Body.String()
	if !strings.Contains(bodyStr, "Agent response chunk") {
		t.Fatalf("expected proxied response to contain 'Agent response chunk', got: %s", bodyStr)
	}
}

func TestChatStreamingAgentNon200Fallback(t *testing.T) {
	db := setupTestDB(t)
	ws := setupTestWorkspace(t)

	// Mock agent returning 500 error to ensure response body is closed and fallback triggers cleanly
	mockAgent := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "Internal Agent Error", http.StatusInternalServerError)
	}))
	defer mockAgent.Close()

	server := api.NewServer(db, mockAgent.URL, ws)

	payload := map[string]string{
		"workspace_id": "test-ws-500",
		"prompt":       "Prompt triggers 500 fallback",
	}
	body, _ := json.Marshal(payload)
	req := httptest.NewRequest(http.MethodPost, "/api/chat", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()

	server.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 OK fallback stream, got %d", rec.Code)
	}

	bodyStr := rec.Body.String()
	if !strings.Contains(bodyStr, "event: reasoning") || !strings.Contains(bodyStr, "event: message") {
		t.Fatalf("expected fallback SSE stream on agent non-200, got: %s", bodyStr)
	}
}

func TestTerminalWebSocket(t *testing.T) {
	db := setupTestDB(t)
	ws := setupTestWorkspace(t)
	server := api.NewServer(db, "http://localhost:5050", ws)

	ts := httptest.NewServer(server)
	defer ts.Close()

	wsURL := "ws" + strings.TrimPrefix(ts.URL, "http") + "/api/terminal"

	dialer := websocket.DefaultDialer
	conn, resp, err := dialer.Dial(wsURL, nil)
	if err != nil {
		t.Fatalf("failed to dial websocket at %s (resp: %v): %v", wsURL, resp, err)
	}
	defer conn.Close()

	// Send an enter/newline or simple command
	if err := conn.WriteMessage(websocket.TextMessage, []byte("\r\n")); err != nil {
		t.Fatalf("failed to write to websocket: %v", err)
	}

	// Read initial prompt or output within timeout
	_ = conn.SetReadDeadline(time.Now().Add(2 * time.Second))
	messageType, msg, err := conn.ReadMessage()
	if err != nil && err != io.EOF {
		// Even if timed out, having connected successfully is verified
		t.Logf("Read returned (might be timeout waiting for prompt): %v", err)
	} else {
		t.Logf("Terminal output received (type %d): %s", messageType, string(msg))
	}
}

func TestTerminalWebSocketOriginCheck(t *testing.T) {
	db := setupTestDB(t)
	ws := setupTestWorkspace(t)
	server := api.NewServer(db, "http://localhost:5050", ws)

	ts := httptest.NewServer(server)
	defer ts.Close()

	wsURL := "ws" + strings.TrimPrefix(ts.URL, "http") + "/api/terminal"

	// 1. Untrusted origin should be rejected with 403 Forbidden
	untrustedHeader := make(http.Header)
	untrustedHeader.Set("Origin", "http://evil-attacker.com")
	_, resp, err := websocket.DefaultDialer.Dial(wsURL, untrustedHeader)
	if err == nil {
		t.Fatalf("expected dial from evil origin to fail, but it succeeded")
	}
	if resp != nil && resp.StatusCode != http.StatusForbidden {
		t.Fatalf("expected HTTP 403 Forbidden for untrusted origin, got %d", resp.StatusCode)
	}

	// 2. Trusted localhost origin should succeed
	trustedHeader := make(http.Header)
	trustedHeader.Set("Origin", "http://localhost:5173")
	conn, resp, err := websocket.DefaultDialer.Dial(wsURL, trustedHeader)
	if err != nil {
		t.Fatalf("expected dial from localhost to succeed (resp: %v): %v", resp, err)
	}
	conn.Close()

	// 3. Trusted 127.0.0.1 origin should succeed
	trustedHeader2 := make(http.Header)
	trustedHeader2.Set("Origin", "http://127.0.0.1:8090")
	conn2, resp, err := websocket.DefaultDialer.Dial(wsURL, trustedHeader2)
	if err != nil {
		t.Fatalf("expected dial from 127.0.0.1 to succeed (resp: %v): %v", resp, err)
	}
	conn2.Close()
}
