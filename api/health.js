export default function handler(req, res) {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  res.status(200).json({
    status: 'ok',
    service: 'adith-ai-studio',
    runtime: 'vercel-serverless',
    provider: {
      provider: 'gemini',
      model: 'gemini-3.1-flash-lite-preview',
      active: true
    }
  });
}
