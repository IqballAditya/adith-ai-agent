export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  const { prompt, model } = req.body || {};
  const apiKey = process.env.GEMINI_API_KEY;

  const sendEvent = (type, content, data) => {
    res.write(`data: ${JSON.stringify({ type, content, data })}\n\n`);
  };

  sendEvent('reasoning', `Analyzing request: "${prompt || 'task'}"\nSelecting model: Google Gemini Flash (${model || 'default'})\nPlanning code generation and AST validation...\n`);

  if (apiKey) {
    try {
      const geminiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`;
      const payload = {
        contents: [
          {
            parts: [
              {
                text: `You are ADITH AI, an advanced AI software engineer and coding assistant in ADITH AI STUDIO created by Iqbal. Help the user clearly, politely, and effectively in Indonesian or English matching their query.\n\nUser Prompt: ${prompt}`
              }
            ]
          }
        ]
      };

      const resp = await fetch(geminiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (resp.ok) {
        const data = await resp.json();
        const replyText = data.candidates?.[0]?.content?.parts?.[0]?.text || "Maaf, tidak dapat menghasilkan jawaban.";
        sendEvent('message', replyText);
        sendEvent('done', '');
        return res.end();
      }
    } catch {
      // Fall through to fallback
    }
  }

  // Graceful simulated AI response if no Gemini API key configured on Vercel
  const fallbackReply = `Halo! Saya **ADITH AI Agent** yang berjalan di **ADITH AI STUDIO (Cloud Demo)**.

Saya menerima pertanyaanmu: *"${prompt || ''}"*

Sistem ini didesain sebagai autonomous AI developer environment dengan:
- **Go Gateway** untuk routing real-time throughput tinggi
- **Python Reasoning Engine** dengan Tree-sitter AST & Google Gemini
- **Monaco Code Editor** interaktif

*(💡 Tips: Kamu bisa menambahkan \`GEMINI_API_KEY\` di dashboard Vercel pada menu Project Settings > Environment Variables untuk mengaktifkan AI live)*`;

  sendEvent('message', fallbackReply);
  sendEvent('done', '');
  res.end();
}
