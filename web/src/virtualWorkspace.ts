import { FileNode } from './types'

export const VIRTUAL_TREE: FileNode[] = [
  {
    name: 'agent',
    path: 'agent',
    is_dir: true,
    size: 0,
    children: [
      {
        name: 'llm',
        path: 'agent/llm',
        is_dir: true,
        size: 0,
        children: [
          { name: 'client.py', path: 'agent/llm/client.py', is_dir: false, size: 4820 }
        ]
      },
      { name: 'orchestrator.py', path: 'agent/orchestrator.py', is_dir: false, size: 7120 },
      { name: 'server.py', path: 'agent/server.py', is_dir: false, size: 3450 },
      { name: 'indexer.py', path: 'agent/indexer.py', is_dir: false, size: 2890 }
    ]
  },
  {
    name: 'cmd',
    path: 'cmd',
    is_dir: true,
    size: 0,
    children: [
      {
        name: 'gateway',
        path: 'cmd/gateway',
        is_dir: true,
        size: 0,
        children: [
          { name: 'main.go', path: 'cmd/gateway/main.go', is_dir: false, size: 2150 }
        ]
      }
    ]
  },
  {
    name: 'examples',
    path: 'examples',
    is_dir: true,
    size: 0,
    children: [
      { name: 'calculator.py', path: 'examples/calculator.py', is_dir: false, size: 1420 },
      { name: 'fibonacci.py', path: 'examples/fibonacci.py', is_dir: false, size: 980 }
    ]
  },
  { name: 'main.py', path: 'main.py', is_dir: false, size: 840 },
  { name: 'README.md', path: 'README.md', is_dir: false, size: 4120 },
  { name: 'go.mod', path: 'go.mod', is_dir: false, size: 550 }
]

export const VIRTUAL_FILES: Record<string, string> = {
  'main.py': `# ADITH AI AGENT - Autonomous Execution Engine
import sys
from agent.orchestrator import AgentOrchestrator

def main():
    print("=" * 60)
    print("  ⚡ ADITH AI AGENT & STUDIO - Running Engine")
    print("=" * 60)
    orchestrator = AgentOrchestrator(workspace_path=".")
    print("✓ Agent initialized successfully.")
    print("✓ AST Parser connected (Tree-sitter).")
    print("✓ Vector Memory active.")
    print("Waiting for prompts or incoming tasks...")

if __name__ == "__main__":
    main()
`,
  'examples/calculator.py': `# Example Calculator Module
class Calculator:
    """A clean, robust calculator engine."""
    def add(self, a: float, b: float) -> float:
        return a + b

    def subtract(self, a: float, b: float) -> float:
        return a - b

    def multiply(self, a: float, b: float) -> float:
        return a * b

    def divide(self, a: float, b: float) -> float:
        if b == 0:
            raise ValueError("Division by zero is undefined")
        return a / b

if __name__ == "__main__":
    calc = Calculator()
    print("10 + 5 =", calc.add(10, 5))
    print("10 * 5 =", calc.multiply(10, 5))
`,
  'examples/fibonacci.py': `# Fibonacci Sequence Generator
def fibonacci(n: int) -> list[int]:
    """Return the first n Fibonacci numbers."""
    if n <= 0:
        return []
    if n == 1:
        return [0]
    seq = [0, 1]
    while len(seq) < n:
        seq.append(seq[-1] + seq[-2])
    return seq

if __name__ == "__main__":
    print("First 10 Fibonacci numbers:", fibonacci(10))
`,
  'agent/orchestrator.py': `# Orchestrator for Multi-Turn Agentic Reasoning
import os
from typing import Dict, Any, List

class AgentOrchestrator:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        self.history: List[Dict[str, Any]] = []

    async def execute_task(self, prompt: str) -> Dict[str, Any]:
        """Plan, generate AST diffs, and return verified patch."""
        print(f"[Orchestrator] Processing: {prompt}")
        return {
            "status": "success",
            "prompt": prompt,
            "actions_taken": ["AST_INSPECT", "DIFF_GENERATED"]
        }
`,
  'agent/server.py': `# FastAPI Agent Server
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="ADITH AI Agent Engine")

class ChatRequest(BaseModel):
    workspace_id: str
    prompt: str
    model: str = "Google Gemini Flash"

@app.get("/health")
def health():
    return {"status": "ok", "service": "agent"}
`,
  'agent/llm/client.py': `# Multi-Provider LLM Client
import os
import requests

class LLMClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

    def generate(self, prompt: str, system: str = "") -> str:
        if not self.api_key:
            return f"Echo response for: {prompt}"
        # Direct Gemini API integration
        return "Generated response"
`,
  'cmd/gateway/main.go': `package main

import (
	"log"
	"net/http"
	"os"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8090"
	}
	log.Printf("⚡ ADITH AI Gateway listening on port :%s", port)
	// Server initialization
}
`,
  'README.md': `# ADITH AI AGENT & STUDIO
Enterprise-grade autonomous developer environment and agent runtime.

## Core Features
- ⚡ **Go High-Performance Gateway (:8090)**
- 🧠 **Python Multi-Turn Reasoning Engine (:5050)**
- 🌳 **Tree-sitter AST & Google Gemini Flash**
- 💻 **React Monaco Editor & Cloud Sandbox**
`,
  'go.mod': `module github.com/iqbal/adith-ai-studio

go 1.21

require (
	github.com/gorilla/websocket v1.5.1
)
`
}
