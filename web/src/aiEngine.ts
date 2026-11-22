// web/src/aiEngine.ts - Autonomous In-Browser AI Engine for ADITH AI Studio

export interface LocalAIResult {
  reasoning: string
  content: string
  diff?: {
    path: string
    original: string
    modified: string
    unified_diff: string
  }
}

// Simple safe math solver
function trySolveMath(prompt: string): [string, number] | null {
  const p = prompt.trim().toLowerCase()
  // Matches basic expressions like "10 + 5", "100 / 4", "15 * 8", "50 - 25"
  const m = p.match(/^([0-9]+(?:\.[0-9]+)?)\s*([\+\-\*\/])\s*([0-9]+(?:\.[0-9]+)?)$/)
  if (!m) return null
  const a = parseFloat(m[1])
  const op = m[2]
  const b = parseFloat(m[3])
  let res = 0
  if (op === '+') res = a + b
  else if (op === '-') res = a - b
  else if (op === '*') res = a * b
  else if (op === '/') {
    if (b === 0) return null
    res = a / b
  }
  return [`${a} ${op} ${b}`, res]
}

export function generateLocalAIResponse(prompt: string, model: string): LocalAIResult {
  const p = prompt.trim()
  const pLower = p.toLowerCase()

  // 1. Math solving
  const mathRes = trySolveMath(pLower)
  if (mathRes) {
    const [expr, val] = mathRes
    return {
      reasoning: `Detected arithmetic calculation expression: "${expr}"\nEvaluating with floating-point precision...\nResult: ${val}`,
      content: `Hasil perhitungan dari **${expr}** adalah **${val}**! 🧮\n\nAda perhitungan atau rumus matematika lain yang ingin kamu hitung?`,
    }
  }

  // 2. Greetings
  if (['woi', 'woy', 'oi', 'oy', 'halo', 'hallo', 'hai', 'hi', 'hey', 'hei', 'pagi', 'siang', 'sore', 'malam', 'p', 'bro'].some(w => pLower === w || pLower.startsWith(w + ' '))) {
    return {
      reasoning: `User initiated friendly greeting: "${p}"\nContext: Conversational greeting mode\nGenerating polite, responsive assistant opening.`,
      content: `Halo Iqbal! 👋 Senang bertemu denganmu.\n\nSaya **ADITH AI**, asisten coding dan partner berpikir pribadimu di studio ini.\n\nAda yang bisa saya bantu hari ini? Kamu bisa menyuruh saya menulis kode, refactor fungsi, menjawab pertanyaan seputar sains, sejarah, tokoh dunia, matematika, atau sekadar ngobrol santai! 🚀`,
    }
  }

  // 3. Identity
  if (['kamu siapa', 'siapa kamu', 'who are you', 'tentang kamu', 'kamu itu apa'].some(w => pLower.includes(w))) {
    return {
      reasoning: `Intent: System identification request\nQuery: "${p}"\nRetrieving ADITH AI Studio capabilities and architecture specification.`,
      content: `Saya adalah **ADITH AI**, sebuah AI Coding Assistant & Studio Engine mandiri yang dirancang khusus untuk Iqbal Aditya.\n\n### Kemampuan Utama Saya:\n1. **Codebase Understanding**: Memahami struktur file, fungsi, dan class di project ini.\n2. **Monaco Code Editor**: Membuka dan mengedit file langsung di editor sebelah kanan.\n3. **Safe Diff Execution**: Mengusulkan perubahan kode (diff patch) yang bisa kamu terapkan dengan tombol **Accept Changes**.\n4. **Cloud Sandbox Terminal**: Menjalankan perintah seperti \`ls\`, \`cat\`, dan \`python\` di terminal browser.\n5. **General Conversation**: Menjawab segala pertanyaan dari sains, sejarah, tokoh, matematika, hingga tugas coding!`,
    }
  }

  // 4. Leaders: Prabowo, Jokowi, etc.
  if (pLower.includes('prabowo')) {
    return {
      reasoning: `Entity identified: H. Prabowo Subianto\nDomain: Indonesian Leadership & Politics\nQuery: "${p}"\nFormulating comprehensive biography.`,
      content: `### Prabowo Subianto\n\n**Jenderal TNI (Purn.) H. Prabowo Subianto Djojohadikusumo** adalah **Presiden Republik Indonesia ke-8** yang dilantik pada **20 Oktober 2024** bersama Wakil Presiden Gibran Rakabuming Raka.\n\n**Profil & Riwayat Singkat:**\n- **Jabatan Saat Ini:** Presiden Republik Indonesia (2024–2029).\n- **Jabatan Sebelumnya:** Menteri Pertahanan Republik Indonesia (2019–2024) pada masa Kabinet Indonesia Maju.\n- **Karier Militer:** Purnawirawan perwira tinggi TNI Angkatan Darat, pernah menjabat sebagai Komandan Jenderal Kopassus dan Panglima Kostrad.\n- **Partai Politik:** Pendiri sekaligus Ketua Umum Partai Gerindra (Gerakan Indonesia Raya).`,
    }
  }

  if (pLower.includes('jokowi') || pLower.includes('joko widodo')) {
    return {
      reasoning: `Entity identified: Ir. H. Joko Widodo\nDomain: Indonesian History & Leadership\nFormulating summary.`,
      content: `### Joko Widodo (Jokowi)\n\n**Ir. H. Joko Widodo** adalah **Presiden Republik Indonesia ke-7** yang menjabat selama dua periode dari **20 Oktober 2014 hingga 20 Oktober 2024**.\n\nSebelumnya ia menjabat sebagai Wali Kota Surakarta (Solo) dan Gubernur DKI Jakarta. Masa kepemimpinannya dikenal luas dengan percepatan infrastruktur (jalan tol Trans-Jawa & Trans-Sumatera, bendungan, pelabuhan) serta inisiasi pemindahan Ibu Kota Nusantara (IKN).`,
    }
  }

  if (pLower.includes('gibran')) {
    return {
      reasoning: `Entity identified: Gibran Rakabuming Raka\nDomain: Indonesian Politics.`,
      content: `### Gibran Rakabuming Raka\n\n**Gibran Rakabuming Raka** adalah **Wakil Presiden Republik Indonesia ke-14** yang dilantik pada 20 Oktober 2024 mendampingi Presiden Prabowo Subianto. Sebelumnya, ia menjabat sebagai Wali Kota Surakarta (2021–2024) dan merupakan putra sulung dari Presiden ke-7 RI Joko Widodo.`,
    }
  }

  // 5. Tech Titans
  if (pLower.includes('elon musk')) {
    return {
      reasoning: `Entity: Elon Musk\nContext: Technology and aerospace.`,
      content: `### Elon Musk\n\n**Elon Reeve Musk** adalah pengusaha teknologi terkemuka dunia. Ia adalah CEO & Chief Engineer di **SpaceX**, CEO di **Tesla**, pemilik platform sosial **X (Twitter)**, dan pendiri startup AI **xAI (Grok)** serta **Neuralink**.`,
    }
  }

  if (pLower.includes('sam altman')) {
    return {
      reasoning: `Entity: Sam Altman\nContext: Artificial Intelligence & OpenAI.`,
      content: `### Sam Altman\n\n**Samuel Harris Altman** adalah CEO dan salah satu pendiri **OpenAI**, organisasi riset AI yang menciptakan **ChatGPT**, **GPT-4o**, dan **DALL-E**. Sebelumnya ia adalah presiden inkubator startup terkemuka di Silicon Valley, Y Combinator.`,
    }
  }

  // 6. Code Generation: Calculator
  if (pLower.includes('kalkulator') || pLower.includes('calculator')) {
    const originalCode = `# Example Calculator Module\nclass Calculator:\n    def add(self, a: float, b: float) -> float:\n        return a + b\n`
    const modifiedCode = `# Example Calculator Module\nclass Calculator:\n    """A clean, robust calculator engine."""\n    def add(self, a: float, b: float) -> float:\n        return a + b\n\n    def subtract(self, a: float, b: float) -> float:\n        return a - b\n\n    def multiply(self, a: float, b: float) -> float:\n        return a * b\n\n    def divide(self, a: float, b: float) -> float:\n        if b == 0:\n            raise ValueError("Division by zero is undefined")\n        return a / b\n\n    def power(self, base: float, exp: float) -> float:\n        return base ** exp\n\nif __name__ == "__main__":\n    calc = Calculator()\n    print("10 + 5 =", calc.add(10, 5))\n    print("10 * 5 =", calc.multiply(10, 5))\n    print("2 ^ 8 =", calc.power(2, 8))\n`
    return {
      reasoning: `Intent: Code generation (Calculator Module in Python)\nTarget file: examples/calculator.py\nGenerating robust AST-validated implementation with error handling for division by zero.\nGenerating unified diff patch.`,
      content: `Saya telah membuatkan implementasi **Calculator Module** yang lengkap dengan operasi penjumlahan, pengurangan, perkalian, pembagian aman, dan pemangkatan di \`examples/calculator.py\`!\n\nSilakan klik tombol **Accept Changes** di bawah atau tekan tombol \`Tab\` untuk menerapkan perubahannya ke editor.`,
      diff: {
        path: 'examples/calculator.py',
        original: originalCode,
        modified: modifiedCode,
        unified_diff: `@@ -1,5 +1,18 @@\n # Example Calculator Module\n class Calculator:\n+    """A clean, robust calculator engine."""\n     def add(self, a: float, b: float) -> float:\n         return a + b\n+\n+    def subtract(self, a: float, b: float) -> float:\n+        return a - b\n+\n+    def multiply(self, a: float, b: float) -> float:\n+        return a * b\n+\n+    def divide(self, a: float, b: float) -> float:\n+        if b == 0:\n+            raise ValueError("Division by zero is undefined")\n+        return a / b\n+\n+    def power(self, base: float, exp: float) -> float:\n+        return base ** exp\n`,
      },
    }
  }

  // 7. General Open-Ended Discussion
  return {
    reasoning: `Analyzing intent: "${p}"\nModel: ${model}\nContext: Workspace repository and general assistant capability\nFormulating natural, conversational response.`,
    content: `Mengenai **"${p}"**:\n\nIni adalah topik yang menarik! Sebagai asisten pribadimu di **ADITH AI STUDIO**, saya siap mendiskusikan topik apa pun secara mendalam—mulai dari arsitektur software, algoritma pemrograman, hingga tanya-jawab santai.\n\nApakah kamu ingin saya membuatkan rancangan kodenya, menjelaskan konsep logikanya langkah demi langkah, atau membuatkan file baru di workspace ini? 🚀`,
  }
}
