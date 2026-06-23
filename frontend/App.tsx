import React, { useState, useRef, useCallback } from 'react';
import { UploadCloud, Download, Loader2, Bot, Cpu, CheckCircle2, AlertCircle, Info, Trash2, MousePointer2, ShieldCheck, Repeat2, Database, Shapes } from 'lucide-react';
import TechStackModal from './components/TechStackModal';
import { VerificationResult, CadDocument, CadView } from './types';
import { runCadAgent, runCadVerifier, runCadCorrector } from './services/agent';
import { cleanupCadPrimitives } from './services/cadCleanup';
import { matchTemplate, generateFromTemplate } from './services/templateMatcher';
import { generateDXF } from './utils/dxf';
import { renderCadToCanvas } from './components/CadCanvas';

const MAX_CORRECTION_LOOPS = 3;
const BRAIN_API = 'http://localhost:5001/api/brain';

const App: React.FC = () => {
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [cadDoc, setCadDoc] = useState<CadDocument | null>(null);
  const [mode, setMode] = useState<'idle' | 'agent-processing' | 'verifying' | 'complete'>('idle');
  const [selectedPrimitiveIdx, setSelectedPrimitiveIdx] = useState<number | null>(null);
  const [status, setStatus] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [verification, setVerification] = useState<VerificationResult | null>(null);
  const [correctionHistory, setCorrectionHistory] = useState<string[]>([]);
  const [brainStatus, setBrainStatus] = useState<string>('');
  const [isTechModalOpen, setIsTechModalOpen] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const correctionLoopRef = useRef(0);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rawBase64Ref = useRef('');
  const fileTypeRef = useRef('');
  const currentSessionRef = useRef('');

  const generateSessionId = () => `cad-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

  const processImage = useCallback(async (base64Data: string, mimeType: string, feedback?: string[]) => {
    setError(null);

    try {
      let doc: CadDocument;

      if (feedback && feedback.length > 0) {
        setStatus(`Self-correction loop ${correctionLoopRef.current}/${MAX_CORRECTION_LOOPS}: addressing feedback...`);
        doc = await runCadCorrector(base64Data, mimeType, feedback);
      } else {
        setStatus('Gemini CAD Intelligence analyzing drawing...');
        doc = await runCadAgent(base64Data, mimeType);
      }

      // Run cleanup
      setStatus('Running shape reconstruction...');
      for (const view of doc.views) {
        view.primitives = cleanupCadPrimitives(view.primitives);
      }

      // Verification
      setMode('verifying');
      setStatus('Verifier Agent is checking quality...');
      const verResult = await runCadVerifier(base64Data, mimeType, doc);
      setVerification(verResult);

      // Template matching
      if (doc.templateMatch && doc.templateMatch.confidence >= 0.6) {
        const templateViews = generateFromTemplate(doc.templateMatch);
        if (templateViews.length > 0) {
          for (const tv of templateViews) {
            doc.views.push({
              name: `${tv.view.toUpperCase()} VIEW (parametric)`,
              scale: 1,
              origin: { x: 0, y: 0 },
              primitives: tv.primitives,
            });
          }
        }
      }

      // Render on canvas
      if (canvasRef.current) {
        const ctx = canvasRef.current.getContext('2d');
        if (ctx) {
          canvasRef.current.width = 1200;
          canvasRef.current.height = doc.views.length * 400;
          renderCadToCanvas(ctx, doc.views, doc.calibration.pixelsPerUnit || 1, 1200, doc.views.length * 400);
        }
      }

      setCadDoc(doc);

      // Auto-correction loop
      if (!verResult.approved && correctionLoopRef.current < MAX_CORRECTION_LOOPS) {
        correctionLoopRef.current += 1;
        setCorrectionHistory(prev => [...prev, ...verResult.feedback]);
        setMode('agent-processing');
        setTimeout(() => processImage(base64Data, mimeType, verResult.feedback), 500);
        return;
      }

      correctionLoopRef.current = 0;
      setMode('complete');
      setStatus('CAD Intelligence complete.');
    } catch (err: any) {
      const msg = err?.message || String(err);
      const stack = err?.stack || '';
      console.error('[CAD Error]', msg, stack);
      // Log full details for debugging
      console.log('[CAD Debug] Error details:', JSON.stringify({
        message: msg,
        name: err?.name,
        status: err?.status,
        code: err?.code,
        details: err?.details,
      }, null, 2));
      // Show detailed error in UI
      if (msg.includes('API_KEY_INVALID') || msg.includes('API key not valid') || msg.includes('API_KEY_SERVICE_DISABLED')) {
        setError('🔑 Gemini API key is invalid. Get a new key at https://aistudio.google.com/apikey and update frontend/.env');
      } else if (msg.includes('PERMISSION_DENIED') || msg.includes('403')) {
        setError('🚫 Permission denied. Your API key may not have access to Gemini API. Enable "Generative Language API" in Google Cloud Console.');
      } else if (msg.includes('not found') || msg.includes('404') || msg.includes('model')) {
        setError('🔍 Model not found. The "gemini-2.5-flash" model may need to be enabled for your API key.');
      } else if (msg.includes('fetch') || msg.includes('network') || msg.includes('Failed to fetch')) {
        setError('🌐 Network error. Check your internet connection.');
      } else if (msg.includes('quota') || msg.includes('429') || msg.includes('RESOURCE_EXHAUSTED')) {
        setError('⏳ API quota exceeded. Wait a few minutes and try again.');
      } else {
        // Show first 200 chars of the actual error
        setError(`❌ ${msg.slice(0, 200)}`);
      }
      setMode('idle');
    }
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    currentSessionRef.current = generateSessionId();
    correctionLoopRef.current = 0;
    setCadDoc(null);
    setVerification(null);
    setError(null);
    setCorrectionHistory([]);
    setMode('agent-processing');
    setStatus('Connecting to Gemini AI...');

    const reader = new FileReader();
    reader.onload = async (event) => {
      const base64 = event.target?.result as string;
      setImageSrc(base64);
      const base64Data = base64.split(',')[1];
      rawBase64Ref.current = base64Data;
      fileTypeRef.current = file.name;
      await processImage(base64Data, file.type);
    };
    reader.readAsDataURL(file);
  };

  const handleExportDXF = () => {
    if (!cadDoc) return;
    const dxfContent = generateDXF(cadDoc);
    const blob = new Blob([dxfContent], { type: 'application/dxf' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${cadDoc.title || 'drawing'}.dxf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const isProcessing = mode === 'agent-processing' || mode === 'verifying';

  const allPrimitives = cadDoc?.views.flatMap(v => v.primitives) || [];

  return (
    <div className="h-screen flex flex-col bg-slate-50 font-sans">
      <TechStackModal isOpen={isTechModalOpen} onClose={() => setIsTechModalOpen(false)} />

      {/* HEADER */}
      <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between flex-shrink-0 shadow-sm z-20">
        <div className="flex items-center space-x-3">
          <div className="bg-gradient-to-br from-indigo-500 to-purple-600 p-2 rounded-xl shadow-inner">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-800 leading-tight tracking-tight">CAD Intelligence Layer</h1>
            <p className="text-xs text-slate-500 font-medium">Shop Drawing Generator — Circle/Arc/Rectangle Detection</p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          {brainStatus && (
            <span className="flex items-center space-x-1 text-xs text-emerald-600 bg-emerald-50 px-2 py-1 rounded-full border border-emerald-200">
              <Database className="w-3 h-3" />
              <span>{brainStatus}</span>
            </span>
          )}
          <button onClick={() => setIsTechModalOpen(true)}
            className="flex items-center space-x-1.5 text-sm font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 px-3 py-1.5 rounded-full transition-colors border border-indigo-100"
          >
            <Info className="w-4 h-4" />
            <span>Tech Stack Info</span>
          </button>
          {imageSrc && !isProcessing && (
            <button onClick={() => { setImageSrc(null); setCadDoc(null); setVerification(null); }}
              className="text-sm font-medium text-slate-500 hover:text-red-600 transition-colors px-3 py-1.5 rounded-full hover:bg-red-50"
            >
              Start Over
            </button>
          )}
        </div>
      </header>

      {/* MAIN */}
      <main className="flex-1 flex overflow-hidden">
        {!imageSrc ? (
          // UPLOAD SCREEN
          <div className="flex-1 flex flex-col items-center justify-center p-6 bg-gradient-to-b from-slate-50 to-slate-100">
            <div className="max-w-2xl text-center mb-10">
              <h2 className="text-4xl font-extrabold text-slate-800 mb-4 tracking-tight">CAD Intelligence</h2>
              <p className="text-slate-600 text-lg leading-relaxed">
                Upload a furniture or architectural drawing. Our AI will detect real CAD primitives — circles, arcs, rectangles — and generate a clean shop drawing with dimensions.
              </p>
            </div>
            <div className="w-full max-w-xl p-12 border-2 border-dashed border-indigo-300 rounded-3xl bg-white hover:border-indigo-500 hover:bg-indigo-50/50 transition-all duration-300 cursor-pointer flex flex-col items-center text-center shadow-xl shadow-indigo-100/20 group"
              onClick={() => fileInputRef.current?.click()}
            >
              <input type="file" ref={fileInputRef} onChange={handleFileUpload} accept="image/png, image/jpeg, image/webp" className="hidden" />
              <div className="bg-indigo-100 p-5 rounded-full mb-6 group-hover:scale-110 transition-transform duration-300">
                <UploadCloud className="w-12 h-12 text-indigo-600" />
              </div>
              <h3 className="text-2xl font-bold text-slate-800 mb-2">Upload Drawing</h3>
              <p className="text-slate-500 font-medium">PNG, JPG, WEBP</p>
            </div>
          </div>
        ) : (
          // RESULT SCREEN
          <div className="flex-1 flex w-full h-full">
            {/* SIDEBAR */}
            <div className="w-80 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col shadow-[4px_0_24px_rgba(0,0,0,0.02)] z-10 overflow-hidden">
              <div className="p-5 border-b border-slate-100 bg-slate-50/80">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center">
                  <Shapes className="w-4 h-4 mr-1.5" /> CAD Status
                </h3>
                {isProcessing ? (
                  <div className="flex items-center space-x-3 text-indigo-700 bg-indigo-100/50 p-3 rounded-xl border border-indigo-200 shadow-sm">
                    <Loader2 className="w-5 h-5 animate-spin flex-shrink-0" />
                    <span className="text-sm font-semibold">{status}</span>
                  </div>
                ) : error ? (
                  <div className="flex flex-col space-y-1">
                    <div className="flex items-start space-x-2 text-red-700 bg-red-50 p-3 rounded-xl border border-red-200 shadow-sm">
                      <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                      <span className="text-sm font-semibold">{error}</span>
                    </div>
                    <button
                      onClick={() => {
                        const key = import.meta.env.VITE_GEMINI_API_KEY;
                        const lines = [
                          '=== API Key Debug ===',
                          `Key found: ${!!key}`,
                          `Key length: ${key?.length || 0}`,
                          `Key starts with: ${key ? key.substring(0, Math.min(12, key.length)) + '...' : 'N/A'}`,
                          `Key format: ${key?.startsWith('AQ.') ? 'Vertex AI API key' : key?.startsWith('AIza') ? 'Gemini API key' : 'Unknown format'}`,
                          '',
                          '=== Instructions ===',
                          '1. Open browser console (F12 > Console tab)',
                          '2. Upload the drawing again',
                          '3. Look for [CAD Error] and [CAD Debug] messages',
                          '4. Share the full error text with SuperRoo',
                          '',
                          '=== Get a new Gemini API key ===',
                          'Visit: https://aistudio.google.com/apikey',
                          'Create a key, then update frontend/.env',
                        ].join('\n');
                        alert(lines);
                      }}
                      className="text-xs text-indigo-600 underline text-left p-1 hover:text-indigo-800"
                    >
                      🐛 Debug: Check API key
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center space-x-2 text-emerald-700 bg-emerald-50 p-3 rounded-xl border border-emerald-200 shadow-sm">
                    <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
                    <span className="text-sm font-semibold">CAD Intelligence Complete</span>
                  </div>
                )}
              </div>

              {/* RESULTS */}
              {cadDoc && !isProcessing && (
                <div className="p-5 flex-1 overflow-y-auto space-y-4">
                  {/* Verification */}
                  {verification && (
                    <div>
                      <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Quality</h3>
                      <div className={`p-3 rounded-xl border text-sm ${verification.approved ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}`}>
                        <div className="flex justify-between mb-1">
                          <span className="font-bold">{verification.approved ? '✅ Approved' : '⚠️ Needs Review'}</span>
                          <span className="font-black">{verification.score}/100</span>
                        </div>
                        <ul className="text-xs space-y-1">
                          {verification.feedback.map((fb, i) => <li key={i} className="text-slate-600">• {fb}</li>)}
                        </ul>
                      </div>
                    </div>
                  )}

                  {/* Views summary */}
                  <div>
                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Views</h3>
                    {cadDoc.views.map((v, i) => (
                      <div key={i} className="text-xs bg-slate-50 p-2 rounded-lg mb-1">
                        <span className="font-semibold">{v.name}</span>
                        <span className="text-slate-500 ml-2">({v.primitives.length} primitives)</span>
                      </div>
                    ))}
                  </div>

                  {/* Primitives summary */}
                  <div>
                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Primitives</h3>
                    {['circle', 'arc', 'rectangle', 'polyline', 'line', 'centerline', 'dimension', 'text'].map(type => {
                      const count = allPrimitives.filter(p => p.type === type).length;
                      if (count === 0) return null;
                      const icons: Record<string, string> = { circle: '⭕', arc: '〰️', rectangle: '▭', polyline: '📏', line: '📐', centerline: '➖', dimension: '📏', text: '🔤' };
                      return (
                        <div key={type} className="flex items-center justify-between text-xs bg-white p-2 rounded-lg border border-slate-100 mb-1">
                          <span>{icons[type] || '•'} {type}</span>
                          <span className="font-bold text-indigo-600">{count}</span>
                        </div>
                      );
                    })}
                    {cadDoc.templateMatch && (
                      <div className="flex items-center space-x-2 text-xs bg-purple-50 p-2 rounded-lg border border-purple-200 mt-2">
                        <span>🧩</span>
                        <span className="font-semibold text-purple-700">{cadDoc.templateMatch.templateName}</span>
                        <span className="text-purple-500">({Math.round(cadDoc.templateMatch.confidence * 100)}%)</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* EXPORT */}
              {cadDoc && !isProcessing && (
                <div className="p-5 bg-white mt-auto border-t border-slate-200">
                  <button onClick={handleExportDXF}
                    disabled={allPrimitives.length === 0}
                    className="w-full flex items-center justify-center space-x-2 px-4 py-3.5 bg-slate-900 text-white rounded-xl text-sm font-bold hover:bg-indigo-600 transition-all shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Download className="w-5 h-5" />
                    <span>Export DXF (CIRCLE/ARC/LWPOLYLINE)</span>
                  </button>
                </div>
              )}
            </div>

            {/* CANVAS */}
            <div className="flex-1 relative overflow-auto bg-slate-200/50">
              <canvas ref={canvasRef}
                className="block mx-auto shadow-2xl"
                style={{ maxWidth: '100%', height: 'auto' }}
              />

              {isProcessing && (
                <div className="absolute inset-0 bg-slate-900/30 backdrop-blur-md flex items-center justify-center z-50">
                  <div className="bg-white p-8 rounded-3xl shadow-2xl flex flex-col items-center max-w-sm text-center border border-slate-100">
                    <div className="relative w-20 h-20 mb-6">
                      <div className="absolute inset-0 border-4 border-indigo-100 rounded-full"></div>
                      <div className="absolute inset-0 border-4 border-indigo-600 rounded-full border-t-transparent animate-spin"></div>
                      <Bot className="absolute inset-0 m-auto w-8 h-8 text-indigo-600" />
                    </div>
                    <h3 className="text-xl font-bold text-slate-800 mb-2">CAD Intelligence</h3>
                    <p className="text-sm text-slate-500">{status}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default App;
