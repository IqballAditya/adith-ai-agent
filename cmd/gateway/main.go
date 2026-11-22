package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"adith-ai-studio/internal/api"
	"adith-ai-studio/internal/database"
)

func getEnv(key, defaultVal string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return defaultVal
}

func main() {
	portFlag := flag.String("port", getEnv("PORT", "8090"), "HTTP gateway port")
	workspaceFlag := flag.String("workspace", getEnv("WORKSPACE_ROOT", "."), "Workspace root directory")
	agentFlag := flag.String("agent", getEnv("AGENT_URL", "http://localhost:5050"), "Python Agent URL")
	dbFlag := flag.String("db", getEnv("DB_PATH", "./adith.db"), "SQLite database path")
	flag.Parse()

	absWorkspace, err := filepath.Abs(*workspaceFlag)
	if err != nil {
		log.Fatalf("failed to resolve workspace root: %v", err)
	}

	db, err := database.InitDB(*dbFlag)
	if err != nil {
		log.Fatalf("failed to initialize database: %v", err)
	}
	defer db.Close()

	if err := database.Migrate(db); err != nil {
		log.Fatalf("failed to run database migrations: %v", err)
	}

	server := api.NewServer(db, *agentFlag, absWorkspace)

	addr := fmt.Sprintf("0.0.0.0:%s", *portFlag)
	httpServer := &http.Server{
		Addr:         addr,
		Handler:      server,
		ReadTimeout:  0, // disabled to support long-lived SSE & WebSocket connections
		WriteTimeout: 0,
	}

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)

	go func() {
		log.Printf("[gateway] Adith AI Studio Gateway listening on http://%s", addr)
		log.Printf("[gateway] Workspace root: %s", absWorkspace)
		log.Printf("[gateway] Python agent URL: %s", *agentFlag)
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("[gateway] listen error: %v", err)
		}
	}()

	<-stop
	log.Println("[gateway] shutting down gracefully...")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := httpServer.Shutdown(ctx); err != nil {
		log.Printf("[gateway] shutdown error: %v", err)
	}
	log.Println("[gateway] stopped")
}
