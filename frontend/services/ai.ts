const API_KEY = import.meta.env.VITE_OPENAI_API_KEY;
const MODEL = import.meta.env.VITE_OPENAI_MODEL || 'gpt-4o';
const OPENAI_URL = 'https://api.openai.com/v1/chat/completions';

export async function detectScaleFromImage(base64Data: string, mimeType: string): Promise<{ detectedScale: string | null, confidence: number }> {
  try {
    if (!API_KEY) throw new Error('VITE_OPENAI_API_KEY not set');

    const res = await fetch(OPENAI_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${API_KEY}`,
      },
      body: JSON.stringify({
        model: MODEL,
        messages: [
          {
            role: 'user',
            content: [
              { type: 'text', text: 'Analyze this architectural drawing. Find any text indicating the drawing scale (e.g., "Scale: 1:100", "1/4\\" = 1\'-0\\"", "NTS"). Return JSON: { "detectedScale": string | null, "confidence": number }' },
              { type: 'image_url', image_url: { url: `data:${mimeType};base64,${base64Data}`, detail: 'high' } },
            ],
          },
        ],
        max_tokens: 500,
        response_format: { type: 'json_object' },
      }),
    });

    if (!res.ok) return { detectedScale: null, confidence: 0 };

    const data = await res.json();
    const text = data?.choices?.[0]?.message?.content;
    if (!text) return { detectedScale: null, confidence: 0 };

    return JSON.parse(text);
  } catch (error) {
    console.error("Error detecting scale:", error);
    return { detectedScale: null, confidence: 0 };
  }
}
