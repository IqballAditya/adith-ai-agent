const VIRTUAL_FILES = {
  "main.py": `# ADITH AI AGENT - Autonomous Execution Engine
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
  "examples/calculator.py": `# Example Calculator Module
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
  "examples/fibonacci.py": `# Fibonacci Sequence Generator
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
  "agent/orchestrator.py": `# Orchestrator for Multi-Turn Agentic Reasoning
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
  "agent/server.py": `# FastAPI Agent Server
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
  "agent/llm/client.py": `# Multi-Provider LLM Client
import os
import requests

class LLMClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

    def generate(self, prompt: str, system: str = "") -> str:
        if not self.api_key:
            return f"Echo response for: {prompt}"
        return "Generated response"
`,
  "cmd/gateway/main.go": `package main

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
}
`,
  "README.md": `# ADITH AI AGENT & STUDIO
Enterprise-grade autonomous developer environment and agent runtime.

## Core Features
- ⚡ **Go High-Performance Gateway (:8090)**
- 🧠 **Python Multi-Turn Reasoning Engine (:5050)**
- 🌳 **Tree-sitter AST & Google Gemini Flash**
- 💻 **React Monaco Editor & Cloud Sandbox**
`,
  "go.mod": `module github.com/iqbal/adith-ai-studio

go 1.21

require (
	github.com/gorilla/websocket v1.5.1
)
`
};

export default function handler(req, res) {
  res.setHeader('Content-Type', 'text/plain; charset=utf-8');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  const filePath = req.query.path || 'main.py';
  const content = VIRTUAL_FILES[filePath] || `// File: ${filePath}\n// ADITH AI Cloud Workspace\n`;
  res.status(200).send(content);
}
