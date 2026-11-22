package test_test

import (
	"bufio"
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
)

// setupE2ETestEnv initializes an isolated workspace folder and SQLite database.
func setupE2ETestEnv(t *testing.T) (string, *sql.DB) {
	t.Helper()
	wsDir := t.TempDir()

	dbPath := filepath.Join(wsDir, "adith_e2e.db")
	db, err := database.InitDB(dbPath)
	if err != nil {
		t.Fatalf("failed to initialize e2e test database: %v", err)
	}

	if err := database.Migrate(db); err != nil {
		db.Close()
		t.Fatalf("failed to run database migrations: %v", err)
	}

	t.Cleanup(func() {
		db.Close()
	})

	return wsDir, db
}

// setupMockAgentServer creates an HTTP test server that implements the Python Agent's
// /health, /v1/agent/index, and /v1/agent/chat endpoints.
func setupMockAgentServer(t *testing.T) *httptest.Server {
	t.Helper()

	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(map[string]string{
			"status":  "ok",
			"service": "adith-ai-agent",
		})
	})

	mux.HandleFunc("/v1/agent/index", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		var req struct {
			WorkspaceID   string `json:"workspace_id"`
			WorkspaceRoot string `json:"workspace_root"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"workspace_id":    req.WorkspaceID,
			"files_indexed":   2,
			"symbols_indexed": 3,
			"status":          "success",
		})
	})

	mux.HandleFunc("/v1/agent/chat", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		var req struct {
			WorkspaceID   string `json:"workspace_id"`
			Prompt        string `json:"prompt"`
			WorkspaceRoot string `json:"workspace_root"`
			Model         string `json:"model"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		flusher, ok := w.(http.Flusher)
		if !ok {
			http.Error(w, "Streaming unsupported", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "text/event-stream")
		w.Header().Set("Cache-Control", "no-cache")
		w.Header().Set("Connection", "keep-alive")
		w.WriteHeader(http.StatusOK)

		// 1. Emit reasoning event
		reasoningJSON, _ := json.Marshal(map[string]interface{}{
			"type":    "reasoning",
			"content": fmt.Sprintf("Analyzing code AST for prompt '%s' in workspace '%s'. Detected addition logic bug.", req.Prompt, req.WorkspaceID),
		})
		fmt.Fprintf(w, "event: reasoning\ndata: %s\n\n", reasoningJSON)
		flusher.Flush()

		// 2. Emit conversational message event
		msgJSON, _ := json.Marshal(map[string]interface{}{
			"type":    "message",
			"content": "I analyzed `calculator.py` and patched the `add` function to use addition instead of subtraction.",
		})
		fmt.Fprintf(w, "event: message\ndata: %s\n\n", msgJSON)
		flusher.Flush()

		// 3. Emit diff event
		originalCode := "def add(a: int, b: int) -> int:\n    return a - b  # bug\n"
		modifiedCode := "def add(a: int, b: int) -> int:\n    return a + b\n"
		unifiedDiff := "--- calculator.py\n+++ calculator.py\n@@ -2 +2 @@\n-    return a - b  # bug\n+    return a + b\n"

		diffJSON, _ := json.Marshal(map[string]interface{}{
			"type": "diff",
			"data": map[string]string{
				"path":         "calculator.py",
				"original":     originalCode,
				"modified":     modifiedCode,
				"unified_diff": unifiedDiff,
			},
		})
		fmt.Fprintf(w, "event: diff\ndata: %s\n\n", diffJSON)
		flusher.Flush()

		// 4. Emit done event
		doneJSON, _ := json.Marshal(map[string]interface{}{
			"type": "done",
			"usage": map[string]int{
				"prompt_tokens":     18,
				"completion_tokens": 46,
			},
		})
		fmt.Fprintf(w, "event: done\ndata: %s\n\n", doneJSON)
		flusher.Flush()
	})

	server := httptest.NewServer(mux)
	t.Cleanup(func() {
		server.Close()
	})
	return server
}

func TestE2EWorkflow(t *testing.T) {
	// 1. Initialize isolated test workspace and SQLite database
	wsDir, db := setupE2ETestEnv(t)

	// 2. Create sample Python and Go files in workspace
	pyFile := filepath.Join(wsDir, "calculator.py")
	originalPyContent := "def add(a: int, b: int) -> int:\n    return a - b  # bug\n"
	if err := os.WriteFile(pyFile, []byte(originalPyContent), 0644); err != nil {
		t.Fatalf("failed to write sample python file: %v", err)
	}

	goFile := filepath.Join(wsDir, "util.go")
	goContent := "package main\n\nfunc Version() string { return \"1.0.0\" }\n"
	if err := os.WriteFile(goFile, []byte(goContent), 0644); err != nil {
		t.Fatalf("failed to write sample go file: %v", err)
	}

	// 3. Set up mock agent server representing Python AI engine
	agentServer := setupMockAgentServer(t)

	// Verify Python agent index endpoint
	indexPayload, _ := json.Marshal(map[string]string{
		"workspace_id":   "e2e-ws",
		"workspace_root": wsDir,
	})
	indexResp, err := http.Post(agentServer.URL+"/v1/agent/index", "application/json", bytes.NewReader(indexPayload))
	if err != nil {
		t.Fatalf("failed calling agent index endpoint: %v", err)
	}
	defer indexResp.Body.Close()
	if indexResp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200 from agent index, got %d", indexResp.StatusCode)
	}
	var indexResult map[string]interface{}
	if err := json.NewDecoder(indexResp.Body).Decode(&indexResult); err != nil {
		t.Fatalf("failed decoding index response: %v", err)
	}
	if indexResult["status"] != "success" {
		t.Fatalf("expected index status 'success', got '%v'", indexResult["status"])
	}

	// 4. Initialize Go Gateway server pointing to mock agent & test workspace
	gwServer := api.NewServer(db, agentServer.URL, wsDir)
	ts := httptest.NewServer(gwServer)
	defer ts.Close()

	// 5. Test Gateway Health check
	healthResp, err := http.Get(ts.URL + "/health")
	if err != nil {
		t.Fatalf("failed to call gateway /health: %v", err)
	}
	defer healthResp.Body.Close()
	if healthResp.StatusCode != http.StatusOK {
		t.Fatalf("expected gateway /health 200, got %d", healthResp.StatusCode)
	}

	// 6. Test File Tree listing
	treeResp, err := http.Get(ts.URL + "/api/tree")
	if err != nil {
		t.Fatalf("failed to call gateway /api/tree: %v", err)
	}
	defer treeResp.Body.Close()
	if treeResp.StatusCode != http.StatusOK {
		t.Fatalf("expected /api/tree 200, got %d", treeResp.StatusCode)
	}
	var treeNodes []workspace.FileNode
	if err := json.NewDecoder(treeResp.Body).Decode(&treeNodes); err != nil {
		t.Fatalf("failed to decode tree nodes: %v", err)
	}
	foundPy := false
	for _, n := range treeNodes {
		if n.Name == "calculator.py" {
			foundPy = true
			break
		}
	}
	if !foundPy {
		t.Fatalf("calculator.py not found in gateway /api/tree: %+v", treeNodes)
	}

	// 7. Test Chat SSE Streaming through Gateway
	chatPayload, _ := json.Marshal(map[string]string{
		"workspace_id": "e2e-ws",
		"prompt":       "fix add bug in calculator.py",
		"model":        "claude-3-5-sonnet",
	})
	chatReq, err := http.NewRequest(http.MethodPost, ts.URL+"/api/chat", bytes.NewReader(chatPayload))
	if err != nil {
		t.Fatalf("failed to construct chat request: %v", err)
	}
	chatReq.Header.Set("Content-Type", "application/json")
	chatReq.Header.Set("Accept", "text/event-stream")

	chatResp, err := http.DefaultClient.Do(chatReq)
	if err != nil {
		t.Fatalf("failed calling gateway /api/chat: %v", err)
	}
	defer chatResp.Body.Close()

	if chatResp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(chatResp.Body)
		t.Fatalf("expected 200 from /api/chat, got %d: %s", chatResp.StatusCode, string(body))
	}

	contentType := chatResp.Header.Get("Content-Type")
	if !strings.Contains(contentType, "text/event-stream") {
		t.Fatalf("expected text/event-stream content type, got: %s", contentType)
	}

	// Parse SSE stream
	scanner := bufio.NewScanner(chatResp.Body)
	var reasoningReceived, messageReceived, diffReceived, doneReceived bool
	var diffData struct {
		Path        string `json:"path"`
		Original    string `json:"original"`
		Modified    string `json:"modified"`
		UnifiedDiff string `json:"unified_diff"`
	}

	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "data: ") {
			dataRaw := strings.TrimPrefix(line, "data: ")
			var evt map[string]interface{}
			if err := json.Unmarshal([]byte(dataRaw), &evt); err == nil {
				switch evt["type"] {
				case "reasoning":
					reasoningReceived = true
				case "message":
					messageReceived = true
				case "diff":
					diffReceived = true
					if d, ok := evt["data"].(map[string]interface{}); ok {
						dataBytes, _ := json.Marshal(d)
						_ = json.Unmarshal(dataBytes, &diffData)
					}
				case "done":
					doneReceived = true
				}
			}
		}
	}

	if !reasoningReceived {
		t.Fatalf("expected reasoning event in chat SSE stream")
	}
	if !messageReceived {
		t.Fatalf("expected message event in chat SSE stream")
	}
	if !diffReceived {
		t.Fatalf("expected diff event in chat SSE stream")
	}
	if !doneReceived {
		t.Fatalf("expected done event in chat SSE stream")
	}

	if diffData.Path != "calculator.py" {
		t.Fatalf("expected diff target path calculator.py, got '%s'", diffData.Path)
	}
	expectedModified := "def add(a: int, b: int) -> int:\n    return a + b\n"
	if diffData.Modified != expectedModified {
		t.Fatalf("unexpected diff modified content:\n%s", diffData.Modified)
	}

	// 8. Test Diff Application via Gateway POST /api/diff/accept
	acceptPayload, _ := json.Marshal(map[string]string{
		"path":     diffData.Path,
		"original": diffData.Original,
		"modified": diffData.Modified,
	})
	acceptResp, err := http.Post(ts.URL+"/api/diff/accept", "application/json", bytes.NewReader(acceptPayload))
	if err != nil {
		t.Fatalf("failed calling /api/diff/accept: %v", err)
	}
	defer acceptResp.Body.Close()

	if acceptResp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(acceptResp.Body)
		t.Fatalf("expected 200 from /api/diff/accept, got %d: %s", acceptResp.StatusCode, string(respBody))
	}

	var acceptResult map[string]interface{}
	if err := json.NewDecoder(acceptResp.Body).Decode(&acceptResult); err != nil {
		t.Fatalf("failed decoding accept diff response: %v", err)
	}
	if acceptResult["status"] != "applied" {
		t.Fatalf("expected status 'applied', got '%v'", acceptResult["status"])
	}

	// 9. Assert file is modified on disk
	diskContent, err := os.ReadFile(pyFile)
	if err != nil {
		t.Fatalf("failed reading modified file on disk: %v", err)
	}
	if string(diskContent) != expectedModified {
		t.Fatalf("file content on disk did not match modified diff!\nExpected:\n%s\nActual:\n%s", expectedModified, string(diskContent))
	}

	// 10. Assert logged in SQLite database: messages table
	var userMsgCount int
	err = db.QueryRow("SELECT COUNT(*) FROM messages WHERE role = 'user' AND content LIKE '%calculator.py%'").Scan(&userMsgCount)
	if err != nil {
		t.Fatalf("failed querying user messages from SQLite: %v", err)
	}
	if userMsgCount < 1 {
		t.Fatalf("expected user message to be recorded in SQLite, got count %d", userMsgCount)
	}

	var asstMsgCount int
	var reasoningText string
	err = db.QueryRow("SELECT COUNT(*), COALESCE(reasoning_content, '') FROM messages WHERE role = 'assistant'").Scan(&asstMsgCount, &reasoningText)
	if err != nil {
		t.Fatalf("failed querying assistant messages from SQLite: %v", err)
	}
	if asstMsgCount < 1 {
		t.Fatalf("expected assistant message in SQLite, got %d", asstMsgCount)
	}
	if !strings.Contains(reasoningText, "Analyzing code AST") {
		t.Fatalf("expected reasoning text to be stored in SQLite messages, got: %s", reasoningText)
	}

	// 11. Assert logged in SQLite database: tool_executions table
	var toolCount int
	var toolName, toolStatus, toolArgs, toolOutput string
	err = db.QueryRow("SELECT COUNT(*), tool_name, status, tool_arguments, tool_output FROM tool_executions WHERE tool_name = 'apply_diff'").
		Scan(&toolCount, &toolName, &toolStatus, &toolArgs, &toolOutput)
	if err != nil {
		t.Fatalf("failed querying tool_executions from SQLite: %v", err)
	}
	if toolCount < 1 {
		t.Fatalf("expected tool_executions record for apply_diff, got count %d", toolCount)
	}
	if toolStatus != "success" {
		t.Fatalf("expected tool status 'success', got '%s'", toolStatus)
	}
	if !strings.Contains(toolArgs, "calculator.py") {
		t.Fatalf("expected tool_arguments to reference calculator.py, got: %s", toolArgs)
	}
	if !strings.Contains(toolOutput, "Successfully applied diff") {
		t.Fatalf("expected tool_output confirmation, got: %s", toolOutput)
	}
}

// TestE2EOfflineFallback verifies the resilient behavior of the Go Gateway
// when the Python agent engine is offline.
func TestE2EOfflineFallback(t *testing.T) {
	wsDir, db := setupE2ETestEnv(t)

	// Use unreachable agent port
	server := api.NewServer(db, "http://127.0.0.1:59998", wsDir)
	ts := httptest.NewServer(server)
	defer ts.Close()

	chatPayload, _ := json.Marshal(map[string]string{
		"workspace_id": "offline-ws",
		"prompt":       "Explain codebase structure",
	})
	resp, err := http.Post(ts.URL+"/api/chat", "application/json", bytes.NewReader(chatPayload))
	if err != nil {
		t.Fatalf("failed posting to /api/chat: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200 OK fallback stream, got %d", resp.StatusCode)
	}

	body, _ := io.ReadAll(resp.Body)
	bodyStr := string(body)
	if !strings.Contains(bodyStr, "event: reasoning") || !strings.Contains(bodyStr, "event: message") {
		t.Fatalf("expected fallback SSE stream with reasoning & message, got: %s", bodyStr)
	}

	// Verify logged to SQLite messages
	var msgCount int
	err = db.QueryRow("SELECT COUNT(*) FROM messages WHERE thread_id = 'thread-offline-ws'").Scan(&msgCount)
	if err != nil {
		t.Fatalf("failed querying messages: %v", err)
	}
	if msgCount < 2 {
		t.Fatalf("expected at least 2 fallback messages recorded, got %d", msgCount)
	}
}

// TestE2ELiveAgentIfAvailable runs end-to-end integration against the live Python agent
// if it is already running on port 5050 (e.g. during manual testing with run-dev.ps1).
// If the live agent is not detected, this test skips automatically without failing.
func TestE2ELiveAgentIfAvailable(t *testing.T) {
	client := &http.Client{Timeout: 500 * time.Millisecond}
	resp, err := client.Get("http://127.0.0.1:5050/health")
	if err != nil || resp.StatusCode != http.StatusOK {
		t.Skip("Live Python agent not active on http://127.0.0.1:5050; skipping live agent smoke test")
		return
	}
	resp.Body.Close()

	wsDir, db := setupE2ETestEnv(t)
	pyFile := filepath.Join(wsDir, "calc.py")
	_ = os.WriteFile(pyFile, []byte("def add(a: int, b: int) -> int:\n    return a - b\n"), 0644)

	gwServer := api.NewServer(db, "http://127.0.0.1:5050", wsDir)
	ts := httptest.NewServer(gwServer)
	defer ts.Close()

	chatPayload, _ := json.Marshal(map[string]string{
		"workspace_id": "live-ws",
		"prompt":       "fix bug in calc.py",
	})
	chatResp, err := http.Post(ts.URL+"/api/chat", "application/json", bytes.NewReader(chatPayload))
	if err != nil {
		t.Fatalf("failed calling chat on live agent: %v", err)
	}
	defer chatResp.Body.Close()
	if chatResp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200 from chat with live agent, got %d", chatResp.StatusCode)
	}
}

