package api

import (
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"runtime"
	"sync"

	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  4096,
	WriteBufferSize: 4096,
	CheckOrigin: func(r *http.Request) bool {
		return true
	},
}

func (s *Server) handleTerminal(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("[terminal] websocket upgrade error: %v", err)
		return
	}
	defer conn.Close()

	var cmd *exec.Cmd
	if runtime.GOOS == "windows" {
		cmd = exec.Command("powershell.exe", "-NoLogo", "-NoExit")
	} else {
		shell := os.Getenv("SHELL")
		if shell == "" {
			shell = "/bin/sh"
		}
		cmd = exec.Command(shell)
	}

	cmd.Dir = s.workspaceRoot
	cmd.Env = os.Environ()

	stdin, err := cmd.StdinPipe()
	if err != nil {
		log.Printf("[terminal] stdin pipe error: %v", err)
		return
	}
	defer stdin.Close()

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		log.Printf("[terminal] stdout pipe error: %v", err)
		return
	}
	defer stdout.Close()

	stderr, err := cmd.StderrPipe()
	if err != nil {
		log.Printf("[terminal] stderr pipe error: %v", err)
		return
	}
	defer stderr.Close()

	if err := cmd.Start(); err != nil {
		log.Printf("[terminal] shell start error: %v", err)
		return
	}

	defer func() {
		if cmd.Process != nil {
			_ = cmd.Process.Kill()
			_ = cmd.Wait()
		}
	}()

	var writeMu sync.Mutex
	writeToWS := func(data []byte) error {
		writeMu.Lock()
		defer writeMu.Unlock()
		return conn.WriteMessage(websocket.BinaryMessage, data)
	}

	var wg sync.WaitGroup
	wg.Add(2)

	streamReader := func(r io.Reader) {
		defer wg.Done()
		buf := make([]byte, 2048)
		for {
			n, readErr := r.Read(buf)
			if n > 0 {
				if writeErr := writeToWS(buf[:n]); writeErr != nil {
					return
				}
			}
			if readErr != nil {
				return
			}
		}
	}

	go streamReader(stdout)
	go streamReader(stderr)

	go func() {
		wg.Wait()
		_ = conn.Close()
	}()

	for {
		_, msg, readErr := conn.ReadMessage()
		if readErr != nil {
			break
		}
		if len(msg) > 0 {
			if _, writeErr := stdin.Write(msg); writeErr != nil {
				break
			}
		}
	}
}
