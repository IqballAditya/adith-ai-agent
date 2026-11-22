export default function handler(req, res) {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  const tree = [
    {
      name: "agent",
      path: "agent",
      is_dir: true,
      size: 0,
      children: [
        {
          name: "llm",
          path: "agent/llm",
          is_dir: true,
          size: 0,
          children: [
            { name: "client.py", path: "agent/llm/client.py", is_dir: false, size: 4820 }
          ]
        },
        { name: "orchestrator.py", path: "agent/orchestrator.py", is_dir: false, size: 7120 },
        { name: "server.py", path: "agent/server.py", is_dir: false, size: 3450 },
        { name: "indexer.py", path: "agent/indexer.py", is_dir: false, size: 2890 }
      ]
    },
    {
      name: "cmd",
      path: "cmd",
      is_dir: true,
      size: 0,
      children: [
        {
          name: "gateway",
          path: "cmd/gateway",
          is_dir: true,
          size: 0,
          children: [
            { name: "main.go", path: "cmd/gateway/main.go", is_dir: false, size: 2150 }
          ]
        }
      ]
    },
    {
      name: "examples",
      path: "examples",
      is_dir: true,
      size: 0,
      children: [
        { name: "calculator.py", path: "examples/calculator.py", is_dir: false, size: 1420 },
        { name: "fibonacci.py", path: "examples/fibonacci.py", is_dir: false, size: 980 }
      ]
    },
    { name: "main.py", path: "main.py", is_dir: false, size: 840 },
    { name: "README.md", path: "README.md", is_dir: false, size: 4120 },
    { name: "go.mod", path: "go.mod", is_dir: false, size: 550 }
  ];
  res.status(200).json(tree);
}
