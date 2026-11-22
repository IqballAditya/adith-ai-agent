package api

import (
	"bufio"
	"bytes"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"adith-ai-studio/internal/workspace"
)

// Server represents the Go Gateway HTTP server.
type Server struct {
	db            *sql.DB
	agentURL      string
	workspaceRoot string
	mux           *http.ServeMux
}

// NewServer initializes and configures a new Gateway Server.
func NewServer(db *sql.DB, agentURL string, workspaceRoot string) *Server {
	cleanRoot := filepath.Clean(workspaceRoot)
	s := &Server{
		db:            db,
		agentURL:      strings.TrimRight(agentURL, "/"),
		workspaceRoot: cleanRoot,
		mux:           http.NewServeMux(),
	}
	s.registerRoutes()
	return s
}

// ServeHTTP delegates to the internal mux wrapped with CORS headers.
func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, Accept")

	if r.Method == http.MethodOptions {
		w.WriteHeader(http.StatusOK)
		return
	}

	s.mux.ServeHTTP(w, r)
}

// Router returns the underlying HTTP handler.
func (s *Server) Router() http.Handler {
	return s
}

func (s *Server) registerRoutes() {
	s.mux.HandleFunc("/health", s.handleHealth)
	s.mux.HandleFunc("/api/tree", s.handleTree)
	s.mux.HandleFunc("/api/file", s.handleFile)
	s.mux.HandleFunc("/api/diff/accept", s.handleDiffAccept)
	s.mux.HandleFunc("/api/chat", s.handleChat)
	s.mux.HandleFunc("/api/terminal", s.handleTerminal)

	// Static asset serving if web/dist exists
	distDir := filepath.Join(s.workspaceRoot, "web", "dist")
	if info, err := os.Stat(distDir); err == nil && info.IsDir() {
		fileServer := http.FileServer(http.Dir(distDir))
		s.mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
			if strings.HasPrefix(r.URL.Path, "/api/") || r.URL.Path == "/health" {
				http.NotFound(w, r)
				return
			}
			filePath := filepath.Join(distDir, filepath.Clean(r.URL.Path))
			if stat, err := os.Stat(filePath); err == nil && !stat.IsDir() {
				fileServer.ServeHTTP(w, r)
				return
			}
			http.ServeFile(w, r, filepath.Join(distDir, "index.html"))
		})
	}
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(map[string]string{
		"status":  "ok",
		"service": "adith-gateway",
	})
}

func (s *Server) handleTree(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	tree, err := workspace.ListFileTree(s.workspaceRoot)
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(tree)
}

func (s *Server) handleFile(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	relPath := r.URL.Query().Get("path")
	if relPath == "" {
		relPath = r.URL.Query().Get("file")
	}
	if relPath == "" {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": "path parameter is required"})
		return
	}

	cleanRoot := filepath.Clean(s.workspaceRoot)
	targetPath := filepath.Clean(filepath.Join(cleanRoot, relPath))

	rel, err := filepath.Rel(cleanRoot, targetPath)
	if err != nil || strings.HasPrefix(rel, "..") || rel == ".." {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": "invalid path: target escapes workspace root"})
		return
	}

	info, err := os.Stat(targetPath)
	if err != nil {
		if os.IsNotExist(err) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusNotFound)
			_ = json.NewEncoder(w).Encode(map[string]string{"error": "file not found"})
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
		return
	}

	if info.IsDir() {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": "target path is a directory"})
		return
	}

	data, err := os.ReadFile(targetPath)
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
		return
	}

	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(data)
}

type diffAcceptRequest struct {
	Path         string `json:"path"`
	RelativePath string `json:"relative_path"`
	Original     string `json:"original"`
	Modified     string `json:"modified"`
}

func (s *Server) handleDiffAccept(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req diffAcceptRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": "invalid json body: " + err.Error()})
		return
	}

	targetPath := req.Path
	if targetPath == "" {
		targetPath = req.RelativePath
	}
	if targetPath == "" {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": "path is required"})
		return
	}

	start := time.Now()
	err := workspace.ApplyDiff(s.workspaceRoot, targetPath, req.Original, req.Modified)
	durationMs := time.Since(start).Milliseconds()

	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		if errors.Is(err, workspace.ErrPathEscapesRoot) {
			w.WriteHeader(http.StatusBadRequest)
			_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}
		if errors.Is(err, workspace.ErrContentMismatch) {
			w.WriteHeader(http.StatusConflict)
			_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
		return
	}

	argsJSON, _ := json.Marshal(map[string]string{"path": targetPath})
	_ = s.logToolExecution("apply_diff", string(argsJSON), "Successfully applied diff", "success", durationMs)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(map[string]interface{}{
		"status": "applied",
		"path":   targetPath,
	})
}

type chatRequest struct {
	WorkspaceID string `json:"workspace_id"`
	Prompt      string `json:"prompt"`
	Model       string `json:"model"`
}

func (s *Server) handleChat(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req chatRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": "invalid json body: " + err.Error()})
		return
	}

	if strings.TrimSpace(req.Prompt) == "" {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": "prompt is required"})
		return
	}

	if req.WorkspaceID == "" {
		req.WorkspaceID = "default"
	}
	if req.Model == "" {
		req.Model = "claude-3-5-sonnet"
	}

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "Streaming unsupported", http.StatusInternalServerError)
		return
	}

	// Forward to Python agent service
	agentPayload, _ := json.Marshal(map[string]interface{}{
		"workspace_id":   req.WorkspaceID,
		"prompt":         req.Prompt,
		"workspace_root": s.workspaceRoot,
		"model":          req.Model,
	})

	agentURL := s.agentURL + "/v1/agent/chat"
	agentReq, err := http.NewRequestWithContext(r.Context(), http.MethodPost, agentURL, bytes.NewReader(agentPayload))
	if err == nil {
		agentReq.Header.Set("Content-Type", "application/json")
		agentReq.Header.Set("Accept", "text/event-stream")

		client := &http.Client{Timeout: 0}
		agentResp, agentErr := client.Do(agentReq)
		if agentErr == nil && agentResp.StatusCode == http.StatusOK {
			defer agentResp.Body.Close()

			w.Header().Set("Content-Type", "text/event-stream")
			w.Header().Set("Cache-Control", "no-cache")
			w.Header().Set("Connection", "keep-alive")
			w.Header().Set("X-Accel-Buffering", "no")
			w.WriteHeader(http.StatusOK)

			reader := bufio.NewReader(agentResp.Body)
			var reasoningBuilder strings.Builder
			var messageBuilder strings.Builder
			var promptTokens, completionTokens int

			for {
				line, readErr := reader.ReadString('\n')
				if len(line) > 0 {
					_, _ = w.Write([]byte(line))
					if line == "\n" || line == "\r\n" {
						flusher.Flush()
					}
					if strings.HasPrefix(line, "data: ") {
						dataStr := strings.TrimSpace(strings.TrimPrefix(line, "data: "))
						var evt map[string]interface{}
						if json.Unmarshal([]byte(dataStr), &evt) == nil {
							evtType, _ := evt["type"].(string)
							if evtType == "reasoning" {
								if c, ok := evt["content"].(string); ok {
									reasoningBuilder.WriteString(c)
								}
							} else if evtType == "message" {
								if c, ok := evt["content"].(string); ok {
									messageBuilder.WriteString(c)
								}
							} else if evtType == "done" {
								if usage, ok := evt["usage"].(map[string]interface{}); ok {
									if pt, ok := usage["prompt_tokens"].(float64); ok {
										promptTokens = int(pt)
									}
									if ct, ok := usage["completion_tokens"].(float64); ok {
										completionTokens = int(ct)
									}
								}
							}
						}
					}
				}
				if readErr != nil {
					break
				}
			}
			flusher.Flush()
			s.logChatInteraction(req.WorkspaceID, req.Prompt, reasoningBuilder.String(), messageBuilder.String(), promptTokens, completionTokens)
			return
		}
	}

	// Agent offline fallback mock stream
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")
	w.WriteHeader(http.StatusOK)

	reasoningMsg := fmt.Sprintf("Offline fallback reasoning: workspace context analyzed for prompt %q", req.Prompt)
	responseMsg := fmt.Sprintf("I analyzed your request offline: %s. Python agent engine is currently unreachable.", req.Prompt)

	fmt.Fprintf(w, "event: reasoning\ndata: {\"type\": \"reasoning\", \"content\": %q}\n\n", reasoningMsg)
	flusher.Flush()

	fmt.Fprintf(w, "event: message\ndata: {\"type\": \"message\", \"content\": %q}\n\n", responseMsg)
	flusher.Flush()

	fmt.Fprintf(w, "event: done\ndata: {\"type\": \"done\", \"usage\": {\"prompt_tokens\": 12, \"completion_tokens\": 24}}\n\n")
	flusher.Flush()

	s.logChatInteraction(req.WorkspaceID, req.Prompt, reasoningMsg, responseMsg, 12, 24)
}

func (s *Server) logToolExecution(toolName, args, output, status string, durationMs int64) error {
	if s.db == nil {
		return nil
	}

	wsID := "default"
	_, _ = s.db.Exec(`INSERT OR IGNORE INTO workspaces (id, name, root_path) VALUES (?, ?, ?)`, wsID, "default", s.workspaceRoot)

	threadID := "default-thread"
	_, _ = s.db.Exec(`INSERT OR IGNORE INTO chat_threads (id, workspace_id, title, model_name) VALUES (?, ?, ?, ?)`, threadID, wsID, "System Audit Thread", "system")

	msgID := fmt.Sprintf("msg-audit-%d", time.Now().UnixNano())
	_, _ = s.db.Exec(`INSERT OR IGNORE INTO messages (id, thread_id, role, content) VALUES (?, ?, 'system', ?)`, msgID, threadID, "Tool Execution: "+toolName)

	execID := fmt.Sprintf("exec-%d", time.Now().UnixNano())
	_, err := s.db.Exec(`INSERT INTO tool_executions (id, message_id, tool_name, tool_arguments, tool_output, status, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?)`,
		execID, msgID, toolName, args, output, status, durationMs)
	return err
}

func (s *Server) logChatInteraction(workspaceID, prompt, reasoning, response string, promptTokens, completionTokens int) {
	if s.db == nil {
		return
	}

	wsID := workspaceID
	if wsID == "" {
		wsID = "default"
	}
	_, _ = s.db.Exec(`INSERT OR IGNORE INTO workspaces (id, name, root_path) VALUES (?, ?, ?)`, wsID, wsID, s.workspaceRoot)

	threadID := "thread-" + wsID
	_, _ = s.db.Exec(`INSERT OR IGNORE INTO chat_threads (id, workspace_id, title, model_name) VALUES (?, ?, ?, ?)`, threadID, wsID, "Chat with Agent", "agent")

	now := time.Now().UnixNano()
	userMsgID := fmt.Sprintf("msg-user-%d", now)
	_, _ = s.db.Exec(`INSERT INTO messages (id, thread_id, role, content, prompt_tokens, completion_tokens) VALUES (?, ?, 'user', ?, ?, 0)`,
		userMsgID, threadID, prompt, promptTokens)

	asstMsgID := fmt.Sprintf("msg-asst-%d", now+1)
	_, _ = s.db.Exec(`INSERT INTO messages (id, thread_id, role, content, reasoning_content, prompt_tokens, completion_tokens) VALUES (?, ?, 'assistant', ?, ?, 0, ?)`,
		asstMsgID, threadID, response, reasoning, completionTokens)
}
