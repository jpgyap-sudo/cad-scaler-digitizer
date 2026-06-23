import { CadDocument, VerificationResult } from '../types';

const API_KEY = import.meta.env.VITE_OPENAI_API_KEY;
const MODEL = import.meta.env.VITE_OPENAI_MODEL || 'gpt-4o';

const OPENAI_URL = 'https://api.openai.com/v1/chat/completions';

async function openaiChat(systemPrompt: string, userPrompt: string, imageBase64: string, mimeType: string): Promise<string> {
  if (!API_KEY) {
    throw new Error('VITE_OPENAI_API_KEY not set. Add your OpenAI API key to frontend/.env');
  }

  console.log(`[CAD Agent] Using OpenAI ${MODEL}, key starts with: ${API_KEY.substring(0, 8)}...`);

  const messages = [
    { role: 'system' as const, content: systemPrompt },
    {
      role: 'user' as const,
      content: [
        { type: 'text' as const, text: userPrompt },
        {
          type: 'image_url' as const,
          image_url: {
            url: `data:${mimeType};base64,${imageBase64}`,
            detail: 'high' as const,
          },
        },
      ],
    },
  ];

  const res = await fetch(OPENAI_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${API_KEY}`,
    },
    body: JSON.stringify({
      model: MODEL,
      messages,
      max_tokens: 4096,
      response_format: { type: 'json_object' },
    }),
  });

  if (!res.ok) {
    const errText = await res.text();
    let detail = errText;
    try {
      const errJson = JSON.parse(errText);
      detail = errJson?.error?.message || errJson?.error?.code || errText;
    } catch {}
    throw new Error(`OpenAI API error (${res.status}): ${detail}`);
  }

  const data = await res.json();
  const text = data?.choices?.[0]?.message?.content;
  if (!text) throw new Error('Empty response from OpenAI');

  return text;
}

const CAD_SYSTEM_PROMPT = `You are a Professional CAD Engineer with 20 years of experience in architectural and furniture design.

You analyze architectural/furniture drawings and return structured CAD documents. Your output must be valid JSON matching the CadDocument schema exactly.

SCHEMA:
{
  "title": "string - Drawing title",
  "views": [
    {
      "name": "string - View name: TOP VIEW, FRONT VIEW, SIDE VIEW, etc.",
      "scale": number,
      "origin": { "x": number, "y": number },
      "primitives": [
        {
          "type": "circle|arc|rectangle|polyline|line|centerline|dimension|text",
          "center": { "x": number, "y": number },
          "radius": number,
          "startAngle": number,
          "endAngle": number,
          "p1": { "x": number, "y": number },
          "p2": { "x": number, "y": number },
          "points": [{ "x": number, "y": number }],
          "closed": boolean,
          "value": number,
          "unit": "string",
          "orientation": "horizontal|vertical|aligned",
          "content": "string",
          "style": "solid|hidden|center|dimension",
          "layer": "string"
        }
      ]
    }
  ],
  "calibration": {
    "found": boolean,
    "pixelsPerUnit": number,
    "originalScale": "string"
  },
  "templateMatch": {
    "templateName": "string",
    "type": "round_pedestal_table|rectangular_table|sofa|cabinet|bed_headboard|chair|custom",
    "parameters": {},
    "confidence": number
  }
}

CRITICAL RULES:
1. A TRUE circle must be returned as ONE circle primitive with type:"circle", center, radius — NOT as small line segments.
2. A rectangle must be returned as ONE rectangle primitive with type:"rectangle", p1, p2, width, height — NOT as 4 separate lines.
3. Centerlines are long thin lines crossing through circle centers.
4. Dimension lines have numeric values. Read them accurately (e.g., "80cm DIA" → value:80, unit:"cm").
5. Read ALL visible text.
6. Use a 0-1000 normalized coordinate system where (0,0) is top-left of the full image.`;

const CAD_USER_PROMPT = `Analyze this architectural/furniture drawing and return a structured CAD document.

TASK 1 — VIEW DETECTION
Identify separate drawing views (TOP VIEW, FRONT VIEW, SIDE VIEW, DETAIL). For each view, give its origin in 0-1000 coords and scale.

TASK 2 — PRIMITIVE DETECTION
For each view, extract ALL visible primitives:
- CIRCLE: center, radius
- ARC: center, radius, startAngle (degrees), endAngle (degrees)
- RECTANGLE: p1 (top-left), p2 (bottom-right), width and height in REAL units
- POLYLINE: points array, closed:true/false
- LINE: p1, p2 for ALL structural lines
- CENTERLINE: p1, p2 for axis/symmetry lines
- DIMENSION: p1, p2, value (numeric), unit, orientation
- TEXT: position, content

TASK 3 — DIMENSION UNDERSTANDING
Read ALL dimension annotations. Use them to calculate pixelsPerUnit.

TASK 4 — TEMPLATE MATCHING
Classify what object this drawing represents:
- round_pedestal_table, rectangular_table, sofa, cabinet, bed_headboard, chair, or custom

Return valid JSON matching the schema above.`;

const VERIFIER_SYSTEM_PROMPT = `You are a strict QA Verifier for CAD extraction. You evaluate the quality of extracted CAD data by comparing it against the original drawing.

Return JSON: { "score": number 0-100, "feedback": string[], "approved": boolean }`;

/**
 * CAD Intelligence Agent: One OpenAI call for full semantic understanding.
 */
export async function runCadAgent(base64Data: string, mimeType: string): Promise<CadDocument> {
  try {
    const text = await openaiChat(CAD_SYSTEM_PROMPT, CAD_USER_PROMPT, base64Data, mimeType);
    const doc = JSON.parse(text) as CadDocument;
    return doc;
  } catch (error) {
    console.error("CAD Agent Error:", error);
    throw error;
  }
}

/**
 * CAD Verifier Agent: Evaluates quality.
 */
export async function runCadVerifier(base64Data: string, mimeType: string, doc: CadDocument): Promise<VerificationResult> {
  try {
    const userPrompt = `Review the original drawing and evaluate this extracted CAD document:

${JSON.stringify({
  title: doc.title,
  viewCount: doc.views?.length || 0,
  viewNames: doc.views?.map(v => v.name) || [],
  primitiveCounts: (doc.views || []).reduce((acc, v) => {
    (v.primitives || []).forEach((p: any) => { acc[p.type] = (acc[p.type] || 0) + 1; });
    return acc;
  }, {} as Record<string, number>),
  calibration: doc.calibration,
  template: doc.templateMatch,
}, null, 2)}

Evaluate:
1. VIEW ACCURACY (0-30): Are all views detected?
2. PRIMITIVE ACCURACY (0-30): Are circles/lines/dimensions correct?
3. CALIBRATION (0-20): Is scale correct?
4. TEMPLATE MATCH (0-20): Is classification correct?

Return JSON: { "score": number 0-100, "feedback": string[], "approved": boolean }`;

    const text = await openaiChat(VERIFIER_SYSTEM_PROMPT, userPrompt, base64Data, mimeType);
    return JSON.parse(text) as VerificationResult;
  } catch (error) {
    console.error("CAD Verifier Error:", error);
    throw error;
  }
}

/**
 * CAD Corrector Agent: Second pass with feedback.
 */
export async function runCadCorrector(base64Data: string, mimeType: string, feedback: string[]): Promise<CadDocument> {
  try {
    const feedbackText = feedback.map((f, i) => `${i + 1}. ${f}`).join('\n');
    const userPrompt = `SECOND PASS — Previous feedback to fix:
${feedbackText}

${CAD_USER_PROMPT}

Pay special attention to fixing each feedback item above.`;

    const text = await openaiChat(CAD_SYSTEM_PROMPT, userPrompt, base64Data, mimeType);
    return JSON.parse(text) as CadDocument;
  } catch (error) {
    console.error("CAD Corrector Error:", error);
    throw error;
  }
}

// Legacy exports
export async function runDigitizationAgent(_base64Data: string, _mimeType: string): Promise<any> {
  throw new Error('Deprecated — use runCadAgent');
}
export async function runVerifierAgent(_base64Data: string, _mimeType: string, _data: any): Promise<VerificationResult> {
  throw new Error('Deprecated — use runCadVerifier');
}
export async function runCorrectionAgent(_base64Data: string, _mimeType: string, _feedback: string[]): Promise<any> {
  throw new Error('Deprecated — use runCadCorrector');
}
