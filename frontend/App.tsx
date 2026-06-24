import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  UploadCloud, Download, Loader2, Bot, Cpu, CheckCircle2, AlertCircle,
  Info, Shapes, Ruler, Image, FileText, ChevronDown, RefreshCw,
  Layers, Crosshair, Eye, Settings
} from 'lucide-react';
import TechStackModal from './components/TechStackModal';
import { VerificationResult, CadDocument } from './types';
import { runCadAgent, runCadVerifier, runCadCorrector } from './services/agent';
import { cleanupCadPrimitives } from './services/cadCleanup';
import { matchTemplate, generateFromTemplate } from './services/templateMatcher';
import { generateDXF } from './utils/dxf';
import { renderCadToCanvas } from './components/CadCanvas';
import {
  digitizeWithBackend, digitizeHybrid, downloadDxf, checkEngineHealth,
  getFurnitureLabel, getFurnitureConfidenceLabel, DigitizeResult
} from './services/cadEngine';

const MAX_CORRECTION_LOOPS = 3;
const BRAIN_API = 'http://localhost:5001/api/brain';

type EngineMode = 'opencv' | 'ai' | 'hybrid';
type ProcessState = 'idle' | 'uploading' | 'processing' | 'complete' | 'error';

const FURNITURE_TYPES = [
  { value: '', label: 'Auto-detect' },
  { value: 'round_pedestal_table', label: 'Round Pedestal Table' },
  { value: 'rectangular_table', label: 'Rectangular Table' },
  { value: 'sofa', label: 'Sofa / Couch' },
  { value: 'cabinet', label: 'Cabinet / Wardrobe' },
  { value: 'bed_headboard', label: 'Bed / Headboard' },
  { value: 'chair', label: 'Chair' },
];

const App: React.FC = () => {
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [cadDoc, setCadDoc] = useState<CadDocument | null>(null);
  const [cadEngineResult, setCadEngineResult] = useState<DigitizeResult | null>(null);
  const [mode, setMode] = useState<'idle' | 'agent-processing' | 'verifying' | 'complete'>('idle');
  const [status, setStatus] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [verification, setVerification] = useState<VerificationResult | null>(null);
  const [braintStatus, setBrainStatus] = useState<string>('');
  const [isTechModalOpen, setIsTechModalOpen] = useState(false);
  const [engineMode, setEngineMode] = useState<EngineMode>('hybrid');
  const [engineHealthy, setEngineHealthy] = useState<boolean | null>(null);
  const [processState, setProcessState] = useState<ProcessState>('idle');
  const [fileName, setFileName] = useState<string>('');

  // Manual dimension inputs
  const [realWidthCm, setRealWidthCm] = useState<string>('');
  const [realHeightCm, setRealHeightCm] = useState<string>('');
  const [furnitureType, setFurnitureType] = useState<string>('');

  const fileInputRef = useRef<HTMLInputElement>(null);
  const correctionLoopRef = useRef(0);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Check engine health on mount
  useEffect(() => {
    checkEngineHealth().then(setEngineHealthy);
  }, []);

  const generateSessionId = () => `cad-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

  /**
   * Process via AI (OpenAI/Gemini) — existing pipeline
   */
  const processWithAI = useCallback(async (base64Data: string, mimeType: string, feedback?: string[]) => {
    setError(null);
    try {
      let doc: CadDocument;

      if (feedback && feedback.length > 0) {
        setStatus(`Self-correction loop ${correctionLoopRef.current}/${MAX_CORRECTION_LOOPS}...`);
        doc = await runCadCorrector(base64Data, mimeType, feedback);
      } else {
        setStatus('AI analyzing drawing...');
        doc = await runCadAgent(base64Data, mimeType);
      }

      setStatus('Running shape reconstruction...');
      for (const view of (doc.views || [])) {
        view.primitives = cleanupCadPrimitives(view.primitives || []);
      }

      setMode('verifying');
      setStatus('Verifier checking quality...');
      const verResult = await runCadVerifier(base64Data, mimeType, doc);
      setVerification(verResult);

      if (doc.templateMatch && (doc.templateMatch.confidence || 0) >= 0.6) {
        const templateViews = generateFromTemplate(doc.templateMatch);
        if (templateViews.length > 0) {
          for (const tv of templateViews) {
            if (!doc.views) doc.views = [];
            doc.views.push({
              name: `${tv.view.toUpperCase()} VIEW (parametric)`,
              scale: 1,
              origin: { x: 0, y: 0 },
              primitives: tv.primitives,
            });
          }
        }
      }

      if (canvasRef.current) {
        const ctx = canvasRef.current.getContext('2d');
        if (ctx) {
          const views = doc.views || [];
          canvasRef.current.width = 1200;
          canvasRef.current.height = Math.max(views.length * 400, 400);
          renderCadToCanvas(ctx, views, doc.calibration?.pixelsPerUnit || 1, 1200, canvasRef.current.height);
        }
      }

      setCadDoc(doc);

      if (!verResult.approved && correctionLoopRef.current < MAX_CORRECTION_LOOPS) {
        correctionLoopRef.current += 1;
        setMode('agent-processing');
        setTimeout(() => processWithAI(base64Data, mimeType, verResult.feedback), 500);
        return;
      }

      correctionLoopRef.current = 0;
      setMode('complete');
      setProcessState('complete');
      setStatus('CAD Intelligence complete.');
    } catch (err: any) {
      const msg = err?.message || String(err);
      if (msg.includes('API_KEY_INVALID') || msg.includes('API key not valid')) {
        setError('🔑 OpenAI API key is invalid. Update frontend/.env');
      } else if (msg.includes('fetch') || msg.includes('network')) {
        setError('🌐 Network error. Check your internet connection.');
      } else {
        setError(`❌ ${msg.slice(0, 200)}`);
      }
      setMode('idle');
      setProcessState('error');
    }
  }, []);

  /**
   * Process via OpenCV Python engine
   */
  const processWithOpenCV = useCallback(async (file: File) => {
    setError(null);
    setProcessState('processing');
    setStatus('Uploading to CAD engine...');

    try {
      const w = realWidthCm ? parseFloat(realWidthCm) : undefined;
      const h = realHeightCm ? parseFloat(realHeightCm) : undefined;
      const ft = furnitureType || undefined;

      const isHybrid = engineMode === 'hybrid';
      setStatus(isHybrid ? 'Hybrid: OpenCV geometry + OpenAI Vision...' : 'Running OpenCV detection + OCR + DXF...');

      const result = isHybrid
        ? await digitizeHybrid(file, { realWidthCm: w, realHeightCm: h, furnitureType: ft })
        : await digitizeWithBackend(file, { realWidthCm: w, realHeightCm: h, furnitureType: ft });

      setCadEngineResult(result);
      setProcessState('complete');
      setMode('complete');
      setStatus(isHybrid ? 'Hybrid engine complete. Cross-validated DXF ready.' : 'OpenCV engine complete. DXF ready for download.');

      const reader = new FileReader();
      reader.onload = (e) => setImageSrc(e.target?.result as string);
      reader.readAsDataURL(file);
    } catch (err: any) {
      setError(`❌ ${err?.message || 'Unknown error'}`);
      setProcessState('error');
      setMode('idle');
    }
  }, [realWidthCm, realHeightCm, furnitureType, engineMode]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target?.files?.[0];
    if (!file) return;

    setFileName(file.name);
    correctionLoopRef.current = 0;
    setCadDoc(null);
    setCadEngineResult(null);
    setVerification(null);
    setError(null);
    setProcessState('processing');

    if (engineMode === 'ai') {
      setMode('agent-processing');
      setStatus('Connecting to AI...');
      const reader = new FileReader();
      reader.onload = async (event) => {
        const base64 = event.target?.result as string;
        setImageSrc(base64);
        const base64Data = base64.split(',')[1];
        await processWithAI(base64Data, file.type);
      };
      reader.readAsDataURL(file);
    } else {
      await processWithOpenCV(file);
    }
  };

  const handleExportDXF = () => {
    if (cadEngineResult) {
      downloadDxf(cadEngineResult);
    } else if (cadDoc) {
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
    }
  };

  const isProcessing = processState === 'processing';
  const allPrimitives = cadDoc?.views?.flatMap(v => v.primitives || []) || [];

  // Summary stats
  const dims = cadEngineResult?.detected?.dimensions || [];
  const detectedFurniture = cadEngineResult?.furniture;

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
            <h1 className="text-lg font-bold text-slate-800 leading-tight tracking-tight">CAD Scaler Digitizer</h1>
            <p className="text-xs text-slate-500 font-medium">Image → Scaled DXF with editable polylines</p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          {/* Engine selector */}
          <div className="flex items-center bg-slate-100 rounded-xl p-0.5 border border-slate-200">
            <button
              onClick={() => setEngineMode('opencv')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                engineMode === 'opencv'
                  ? 'bg-white text-indigo-600 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <Cpu className="w-3.5 h-3.5" />
              <span>OpenCV</span>
            </button>
            <button
              onClick={() => setEngineMode('hybrid')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                engineMode === 'hybrid'
                  ? 'bg-white text-purple-600 shadow-sm ring-2 ring-purple-300'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <Bot className="w-3.5 h-3.5" />
              <span>Hybrid</span>
            </button>
            <button
              onClick={() => setEngineMode('ai')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                engineMode === 'ai'
                  ? 'bg-white text-indigo-600 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <Bot className="w-3.5 h-3.5" />
              <span>AI</span>
            </button>
          </div>

          {/* Engine health */}
          {engineHealthy !== null && engineMode === 'opencv' && (
            <span className={`flex items-center space-x-1 text-xs px-2 py-1 rounded-full border ${
              engineHealthy
                ? 'text-emerald-600 bg-emerald-50 border-emerald-200'
                : 'text-amber-600 bg-amber-50 border-amber-200'
            }`}>
              <Cpu className="w-3 h-3" />
              <span>{engineHealthy ? 'Engine Online' : 'Engine Offline'}</span>
            </span>
          )}

          <button onClick={() => setIsTechModalOpen(true)}
            className="flex items-center space-x-1.5 text-sm font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 px-3 py-1.5 rounded-full transition-colors border border-indigo-100"
          >
            <Info className="w-4 h-4" />
            <span>Info</span>
          </button>
        </div>
      </header>

      {/* MAIN */}
      <main className="flex-1 flex overflow-hidden">
        {!imageSrc && processState === 'idle' ? (
          // === UPLOAD SCREEN ===
          <div className="flex-1 flex flex-col items-center justify-center p-6 bg-gradient-to-b from-slate-50 to-slate-100 overflow-y-auto">
            <div className="max-w-2xl text-center mb-8">
              <h2 className="text-4xl font-extrabold text-slate-800 mb-4 tracking-tight">
                Furniture Drawing → Scaled DXF
              </h2>
              <p className="text-slate-600 text-lg leading-relaxed mb-4">
                Upload a furniture drawing with written dimensions. Our engine will detect lines,
                read dimensions via OCR, identify the furniture type, and generate a clean,
                editable DXF file with properly scaled polylines.
              </p>
              <p className="text-slate-500 text-sm">
                Supports PNG, JPEG, PDF &bull; Template-based reconstruction for tables, sofas, cabinets, chairs, beds
              </p>
            </div>

            {/* Dimension input fields */}
            <div className="w-full max-w-xl mb-6 p-5 bg-white rounded-2xl shadow-sm border border-slate-200">
              <h3 className="text-sm font-bold text-slate-700 mb-3 flex items-center">
                <Ruler className="w-4 h-4 mr-2" />
                Optional: Known Dimensions (for accurate scale)
              </h3>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Width (cm)</label>
                  <input
                    type="number"
                    value={realWidthCm}
                    onChange={e => setRealWidthCm(e.target.value)}
                    placeholder="e.g. 80"
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Height (cm)</label>
                  <input
                    type="number"
                    value={realHeightCm}
                    onChange={e => setRealHeightCm(e.target.value)}
                    placeholder="e.g. 70"
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>
              </div>

              {/* Furniture type override */}
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Furniture Type</label>
                <select
                  value={furnitureType}
                  onChange={e => setFurnitureType(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                >
                  {FURNITURE_TYPES.map(ft => (
                    <option key={ft.value} value={ft.value}>{ft.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Upload area */}
            <div
              className="w-full max-w-xl p-12 border-2 border-dashed border-indigo-300 rounded-3xl bg-white hover:border-indigo-500 hover:bg-indigo-50/50 transition-all duration-300 cursor-pointer flex flex-col items-center text-center shadow-xl shadow-indigo-100/20 group"
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileUpload}
                accept="image/png,image/jpeg,image/jpg,image/webp,application/pdf"
                className="hidden"
              />
              <div className="bg-indigo-100 p-5 rounded-full mb-6 group-hover:scale-110 transition-transform duration-300">
                <UploadCloud className="w-12 h-12 text-indigo-600" />
              </div>
              <h3 className="text-2xl font-bold text-slate-800 mb-2">Upload Drawing</h3>
              <p className="text-slate-500 font-medium">PNG, JPEG, PDF &bull; Click to browse</p>
              {engineMode === 'opencv' && !engineHealthy && (
                <p className="text-amber-500 text-xs mt-2">⚠️ Python engine not detected — start the backend first</p>
              )}
            </div>
          </div>
        ) : (
          // === RESULT SCREEN ===
          <div className="flex-1 flex w-full h-full">
            {/* SIDEBAR */}
            <div className="w-80 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col shadow-[4px_0_24px_rgba(0,0,0,0.02)] z-10 overflow-hidden">
              <div className="p-5 border-b border-slate-100 bg-slate-50/80">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center">
                  <Shapes className="w-4 h-4 mr-1.5" /> Status
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
                      onClick={() => { setImageSrc(null); setCadEngineResult(null); setCadDoc(null); setProcessState('idle'); }}
                      className="text-xs text-indigo-600 underline text-left p-1 hover:text-indigo-800"
                    >
                      ← Try again
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center space-x-2 text-emerald-700 bg-emerald-50 p-3 rounded-xl border border-emerald-200 shadow-sm">
                    <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
                    <span className="text-sm font-semibold">Complete</span>
                  </div>
                )}
              </div>

              {/* RESULTS - OpenCV Engine */}
              {cadEngineResult && !isProcessing && (
                <div className="p-5 flex-1 overflow-y-auto space-y-4">
                  {/* File info */}
                  <div className="text-xs text-slate-500 bg-slate-50 p-2 rounded-lg flex items-center space-x-2">
                    <FileText className="w-3.5 h-3.5" />
                    <span className="truncate">{fileName}</span>
                  </div>

                  {/* Furniture type */}
                  {detectedFurniture && (
                    <div>
                      <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Furniture</h3>
                      <div className="bg-purple-50 p-3 rounded-xl border border-purple-200">
                        <div className="flex justify-between">
                          <span className="font-bold text-sm text-purple-700">
                            {getFurnitureLabel(detectedFurniture.type)}
                          </span>
                          <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                            detectedFurniture.confidence >= 0.8
                              ? 'bg-emerald-100 text-emerald-700'
                              : detectedFurniture.confidence >= 0.5
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-slate-200 text-slate-600'
                          }`}>
                            {getFurnitureConfidenceLabel(detectedFurniture.confidence)}
                          </span>
                        </div>
                        <div className="text-xs text-slate-500 mt-1">
                          Confidence: {Math.round(detectedFurniture.confidence * 100)}%
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Detected Features */}
                  <div>
                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                      <Layers className="w-3 h-3 inline mr-1" /> Detected
                    </h3>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="bg-slate-50 p-2 rounded-lg text-center">
                        <div className="text-lg font-bold text-indigo-600">{cadEngineResult.detected?.lines ?? 0}</div>
                        <div className="text-xs text-slate-500">Lines</div>
                      </div>
                      <div className="bg-slate-50 p-2 rounded-lg text-center">
                        <div className="text-lg font-bold text-indigo-600">{cadEngineResult.detected?.circles ?? 0}</div>
                        <div className="text-xs text-slate-500">Circles</div>
                      </div>
                      <div className="bg-slate-50 p-2 rounded-lg text-center">
                        <div className="text-lg font-bold text-indigo-600">{cadEngineResult.detected?.rectangles ?? 0}</div>
                        <div className="text-xs text-slate-500">Rectangles</div>
                      </div>
                      <div className="bg-slate-50 p-2 rounded-lg text-center">
                        <div className="text-lg font-bold text-indigo-600">{dims.length}</div>
                        <div className="text-xs text-slate-500">Dimensions</div>
                      </div>
                    </div>
                  </div>

                  {/* OCR Dimensions */}
                  {dims.length > 0 && (
                    <div>
                      <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                        <Eye className="w-3 h-3 inline mr-1" /> OCR Dimensions
                      </h3>
                      <div className="space-y-1 max-h-32 overflow-y-auto">
                        {dims.map((d, i) => (
                          <div key={i} className="text-xs bg-slate-50 p-2 rounded-lg flex justify-between">
                            <span className="font-semibold">{d.raw}</span>
                            <span className="text-indigo-600">{d.value_cm} cm</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Warnings */}
                  {(cadEngineResult.warnings || []).length > 0 && (
                    <div>
                      <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Notes</h3>
                      <ul className="text-xs space-y-1">
                        {(cadEngineResult.warnings || []).map((w, i) => (
                          <li key={i} className="text-amber-700 bg-amber-50 p-2 rounded-lg">• {w}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* OCR text snippet */}
                  {(cadEngineResult.detected?.ocr_lines || []).length > 0 && (
                    <div>
                      <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">OCR Text</h3>
                      <div className="text-xs bg-slate-50 p-2 rounded-lg max-h-24 overflow-y-auto font-mono">
                        {(cadEngineResult.detected?.ocr_lines || []).slice(0, 10).map((line, i) => (
                          <div key={i}>{line}</div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* RESULTS - AI Engine */}
              {cadDoc && !isProcessing && (
                <div className="p-5 flex-1 overflow-y-auto space-y-4">
                  {verification && (
                    <div>
                      <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Quality</h3>
                      <div className={`p-3 rounded-xl border text-sm ${
                        verification.approved ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'
                      }`}>
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

                  <div>
                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Views</h3>
                    {cadDoc.views.map((v, i) => (
                      <div key={i} className="text-xs bg-slate-50 p-2 rounded-lg mb-1">
                        <span className="font-semibold">{v.name}</span>
                        <span className="text-slate-500 ml-2">({v.primitives.length} primitives)</span>
                      </div>
                    ))}
                  </div>

                  <div>
                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Primitives</h3>
                    {['circle', 'arc', 'rectangle', 'polyline', 'line', 'centerline', 'dimension', 'text'].map(type => {
                      const count = allPrimitives.filter(p => p.type === type).length;
                      if (count === 0) return null;
                      const icons: Record<string, string> = {
                        circle: '⭕', arc: '〰️', rectangle: '▭', polyline: '📏',
                        line: '📐', centerline: '➖', dimension: '📏', text: '🔤'
                      };
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
              {((cadEngineResult || cadDoc) && !isProcessing) && (
                <div className="p-5 bg-white mt-auto border-t border-slate-200">
                  <button
                    onClick={handleExportDXF}
                    className="w-full flex items-center justify-center space-x-2 px-4 py-3.5 bg-slate-900 text-white rounded-xl text-sm font-bold hover:bg-indigo-600 transition-all shadow-lg"
                  >
                    <Download className="w-5 h-5" />
                    <span>{cadEngineResult ? 'Download DXF (Scaled)' : 'Export DXF'}</span>
                  </button>
                  <button
                    onClick={() => { setImageSrc(null); setCadEngineResult(null); setCadDoc(null); setProcessState('idle'); }}
                    className="w-full text-xs text-slate-500 py-2 mt-2 hover:text-slate-700 transition-colors"
                  >
                    ← Upload another drawing
                  </button>
                </div>
              )}
            </div>

            {/* CANVAS / PREVIEW */}
            <div className="flex-1 relative overflow-auto bg-slate-200/50">
              {cadEngineResult && (
                <div className="p-6">
                  <div className="bg-white rounded-2xl shadow-lg p-4 mb-4">
                    <h3 className="text-sm font-bold text-slate-700 mb-3 flex items-center">
                      <Image className="w-4 h-4 mr-2" />
                      Uploaded Drawing
                    </h3>
                    {imageSrc && (
                      <img src={imageSrc} alt="Uploaded drawing" className="max-w-full max-h-[500px] mx-auto rounded-lg" />
                    )}
                  </div>
                  <div className="bg-white rounded-2xl shadow-lg p-4">
                    <h3 className="text-sm font-bold text-slate-700 mb-2 flex items-center">
                      <Settings className="w-4 h-4 mr-2" />
                      Result Summary
                    </h3>
                    <div className="text-sm text-slate-600 space-y-1">
                      <p>🏷️ Furniture: <strong>{detectedFurniture ? getFurnitureLabel(detectedFurniture.type || '') : 'N/A'}</strong></p>
                      <p>📐 Lines: <strong>{cadEngineResult.detected?.lines ?? 0}</strong> | Circles: <strong>{cadEngineResult.detected?.circles ?? 0}</strong> | Rects: <strong>{cadEngineResult.detected?.rectangles ?? 0}</strong></p>
                      <p>🔤 OCR Dimensions: <strong>{dims.length}</strong></p>
                      <p>💾 DXF: <strong>{cadEngineResult.dxf_file}</strong></p>
                    </div>
                  </div>
                </div>
              )}

              <canvas
                ref={canvasRef}
                className="block mx-auto shadow-2xl"
                style={{ maxWidth: '100%', height: 'auto' }}
              />

              {isProcessing && (
                <div className="absolute inset-0 bg-slate-900/30 backdrop-blur-md flex items-center justify-center z-50">
                  <div className="bg-white p-8 rounded-3xl shadow-2xl flex flex-col items-center max-w-sm text-center border border-slate-100">
                    <div className="relative w-20 h-20 mb-6">
                      <div className="absolute inset-0 border-4 border-indigo-100 rounded-full"></div>
                      <div className="absolute inset-0 border-4 border-indigo-600 rounded-full border-t-transparent animate-spin"></div>
                      {engineMode === 'opencv' ? (
                        <Cpu className="absolute inset-0 m-auto w-8 h-8 text-indigo-600" />
                      ) : (
                        <Bot className="absolute inset-0 m-auto w-8 h-8 text-indigo-600" />
                      )}
                    </div>
                    <h3 className="text-xl font-bold text-slate-800 mb-2">
                      {engineMode === 'opencv' ? 'Processing Drawing' : 'AI Analyzing'}
                    </h3>
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
