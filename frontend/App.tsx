import React, { useState, useRef, useCallback, useEffect, Component, ErrorInfo, ReactNode } from 'react';
import {
  UploadCloud, Download, Loader2, Bot, Cpu, CheckCircle2, AlertCircle,
  Info, Shapes, Ruler, Image, FileText, ChevronDown, RefreshCw,
  Layers, Crosshair, Eye, Settings, Play, Shield, Sparkles
} from 'lucide-react';
import TechStackModal from './components/TechStackModal';
import ChatBox from './components/ChatBox';
import SliderPanel from './components/SliderPanel';
import InteractiveSvgPreview from './components/InteractiveSvgPreview';
import BrainStats from './components/BrainStats';
import ConfidencePanel, { DimItem } from './components/ConfidencePanel';
import NavBar, { Tab } from './components/NavBar';
import WorkflowGuide from './components/WorkflowGuide';
import TemplatesPage from './components/TemplatesPage';
import CalibrationPage from './components/CalibrationPage';
import ResourcesPage from './components/ResourcesPage';
import AnalyticsPage from './components/AnalyticsPage';
import ImprovementsPage from './components/ImprovementsPage';
import { VerificationResult, CadDocument } from './types';
import { runCadAgent, runCadVerifier, runCadCorrector } from './services/agent';
import { cleanupCadPrimitives } from './services/cadCleanup';
import { matchTemplate, generateFromTemplate, getSourceLabel, getSourceColor } from './services/templateMatcher';
import { generateDXF } from './utils/dxf';
import { renderCadToCanvas } from './components/CadCanvas';
import PipelineUpload, { PipelineJobResult } from './components/PipelineUpload';
import CrawlInput from './components/CrawlInput';
import SmartConfirmations from './components/SmartConfirmations';
import PipelineProgress from './components/PipelineProgress';
import DXFPreview from './components/DXFPreview';
import ReviewPanel from './components/ReviewPanel';
import {
  digitizeWithBackend, digitizeHybrid, downloadDxf, checkEngineHealth,
  resolveTemplate, digitizeUnified,
  getFurnitureLabel, getFurnitureConfidenceLabel, DigitizeResult,
  getPreviewUrl, getPdfUrl, getSvgPreviewUrl
} from './services/cadEngine';
import { useAppVersion } from './hooks/useAppVersion';

// ─── Global Error Boundary ────────────────────────────────────────────────────
interface ErrorBoundaryState { hasError: boolean; message: string; }
class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, message: '' };
  }
  static getDerivedStateFromError(err: Error): ErrorBoundaryState {
    return { hasError: true, message: err?.message || String(err) };
  }
  componentDidCatch(err: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', err, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="h-screen flex flex-col items-center justify-center bg-slate-50 p-8">
          <div className="bg-white border border-red-200 rounded-2xl p-8 max-w-lg shadow-lg text-center">
            <div className="text-4xl mb-4">⚠️</div>
            <h2 className="text-xl font-bold text-slate-800 mb-2">Something went wrong</h2>
            <p className="text-sm text-red-600 bg-red-50 rounded-lg p-3 mb-4 font-mono break-words">{this.state.message}</p>
            <button
              onClick={() => { this.setState({ hasError: false, message: '' }); window.location.reload(); }}
              className="px-6 py-2 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition-colors"
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const MAX_CORRECTION_LOOPS = 3;
const BRAIN_API_BASE = import.meta.env.VITE_BRAIN_API_URL || '';
const BRAIN_API = BRAIN_API_BASE
  ? `${BRAIN_API_BASE}/api/brain`
  : '/api/brain';

type EngineMode = 'opencv' | 'ai' | 'hybrid' | 'pipeline' | 'smart';
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
  const { updateAvailable } = useAppVersion();
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [cadDoc, setCadDoc] = useState<CadDocument | null>(null);
  const [cadEngineResult, setCadEngineResult] = useState<DigitizeResult | null>(null);
  const [pipelineResult, setPipelineResult] = useState<PipelineJobResult | null>(null);
  const [mode, setMode] = useState<'idle' | 'agent-processing' | 'verifying' | 'complete'>('idle');
  const [status, setStatus] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [verification, setVerification] = useState<VerificationResult | null>(null);
  const [braintStatus, setBrainStatus] = useState<string>('');
  const [isTechModalOpen, setIsTechModalOpen] = useState(false);
  const [currentTab, setCurrentTab] = useState<Tab>('upload');
  const [engineMode, setEngineMode] = useState<EngineMode>('hybrid');
  const [engineHealthy, setEngineHealthy] = useState<boolean | null>(null);
  const [processState, setProcessState] = useState<ProcessState>('idle');
  const [fileName, setFileName] = useState<string>('');
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [chatState, setChatState] = useState<any>({});
  const [previewSvgVersion, setPreviewSvgVersion] = useState(0);
  const [svgPreviewUrl, setSvgPreviewUrl] = useState<string>('');
  const [currentDims, setCurrentDims] = useState<Record<string, number>>({
    top_diameter_cm: 80, overall_height_cm: 70, base_diameter_cm: 44,
    neck_diameter_cm: 22.4, top_thickness_cm: 4,
  });
  const [showConfidencePanel, setShowConfidencePanel] = useState(false);
  const [correctionCount, setCorrectionCount] = useState(0);
  const [highlightedComponent, setHighlightedComponent] = useState<string | null>(null);
  const FLAT_COMPONENT_TO_SLIDER: Record<string, string> = {
    tabletop: 'top_diameter_cm',
    collar_plate: 'top_thickness_cm',
    neck_ring: 'neck_diameter_cm',
    pedestal_body: 'base_diameter_cm',
    base_plate: 'base_diameter_cm',
  };
  const [highlightedSliderKey, setHighlightedSliderKey] = useState<string | null>(null);
  const handlePartClick = (component: string) => {
    setHighlightedComponent(component);
    const key = FLAT_COMPONENT_TO_SLIDER[component];
    if (key) setHighlightedSliderKey(key);
  };

  const [realWidthCm, setRealWidthCm] = useState<string>('');
  const [realHeightCm, setRealHeightCm] = useState<string>('');
  const [furnitureType, setFurnitureType] = useState<string>('');
  const [selectedPreset, setSelectedPreset] = useState<string>('');

  const fileInputRef = useRef<HTMLInputElement>(null);
  const correctionLoopRef = useRef(0);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    checkEngineHealth().then(setEngineHealthy);
  }, []);

  const generateSessionId = () => `cad-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

  const processWithAI = useCallback(async (base64Data: string, mimeType: string, feedback?: string[]) => {
    // ... (kept from original)
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

  const processWithOpenCV = useCallback(async (file: File) => {
    // ... (kept from original)
    setError(null);
    setProcessState('processing');
    setStatus('Uploading to CAD engine...');
    try {
      const w = realWidthCm ? parseFloat(realWidthCm) : undefined;
      const h = realHeightCm ? parseFloat(realHeightCm) : undefined;
      const ft = furnitureType || undefined;
      const isHybrid = engineMode === 'hybrid';
      const isSmart = engineMode === 'smart';
      setStatus(isSmart ? 'Smart: AI Vision + OpenCV + Templates...' :
               isHybrid ? 'Hybrid: OpenCV geometry + OpenAI Vision...' :
               'Running OpenCV detection + OCR + DXF...');
      let result: any;
      if (isSmart) {
        result = await digitizeUnified(file, { realWidthCm: w, realHeightCm: h, furnitureType: ft });
      } else if (isHybrid) {
        result = await digitizeHybrid(file, { realWidthCm: w, realHeightCm: h, furnitureType: ft });
      } else {
        result = await digitizeWithBackend(file, { realWidthCm: w, realHeightCm: h, furnitureType: ft });
      }
      setCadEngineResult(result);
      setProcessState('complete');
      setMode('complete');
      setStatus(isSmart ? 'Smart engine complete.' : isHybrid ? 'Hybrid engine complete.' : 'OpenCV engine complete.');
      if (result.resolved_dimensions) setCurrentDims(result.resolved_dimensions);
      if (result.preview_svg) { setSvgPreviewUrl(result.preview_svg); setPreviewSvgVersion(v => v + 1); }
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
    setCadDoc(null);
    setCadEngineResult(null);
    setVerification(null);
    setError(null);
    setMode('idle');
    setProcessState('idle');
    setPendingFile(file);
    setImageSrc(null);
    const reader = new FileReader();
    reader.onload = (ev) => setImageSrc(ev.target?.result as string);
    reader.readAsDataURL(file);
  };

  const handleStart = async () => {
    if (!pendingFile) return;
    const file = pendingFile;
    setPendingFile(null);
    correctionLoopRef.current = 0;
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

  const handleChatRender = (newState: any) => {
    setChatState(newState);
    setPreviewSvgVersion(v => v + 1);
    console.log('[Chat] Render requested, state:', newState);

    // === Gap #1c: Furniture type re-dispatch ===
    // When the user says "this is actually a cabinet", the chat agent sets
    // state.furniture_type — re-digitize with the corrected type.
    const newType = newState?.furniture_type;
    if (newType && cadEngineResult && newType !== cadEngineResult.furniture?.type) {
      console.log('[Chat] Furniture type changed:', cadEngineResult.furniture?.type, '->', newType);
      if (cadEngineResult?.dxf_file) {
        // Re-digitize by calling /digitize/resolve to get new template + parameter schema
        resolveTemplate(newType, {
          widthCm: cadEngineResult.resolved_dimensions?.width_cm || cadEngineResult.resolved_dimensions?.top_diameter_cm,
          heightCm: cadEngineResult.resolved_dimensions?.overall_height_cm,
          depthCm: cadEngineResult.resolved_dimensions?.depth_cm,
        }).then(resolveResult => {
          console.log('[Chat] Re-resolved template:', resolveResult.template_name);
          // The UI will show the new parameter schema; user can then digitize
        }).catch(err => {
          console.error('[Chat] Re-resolve failed:', err);
        });
      }
    }

    // === Gap #5: Notes forwarding ===
    // When the chat agent sets state.notes, send to existing /adjust or /chat
    // with a drawing_note parameter. The backend stores notes in the sidecar.
    if (newState?.notes && cadEngineResult?.dxf_file) {
      try {
        const notesForm = new FormData();
        notesForm.append('dxf_file', cadEngineResult.dxf_file);
        notesForm.append('materials', JSON.stringify({})); // preserve materials
        // Also include current dimensions so the /adjust preserves them
        if (newState?.dimensions) {
          for (const [k, v] of Object.entries(newState.dimensions)) {
            notesForm.append(k, String(v));
          }
        }
        fetch('/py-api/adjust', { method: 'POST', body: notesForm })
          .then(() => console.log('[Chat] Notes forwarded via /adjust'))
          .catch(err => console.error('[Chat] Notes forward failed:', err));
      } catch (e) {
        console.error('[Chat] Notes forward error:', e);
      }
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

  const confidenceDims: DimItem[] = React.useMemo(() => {
    if (!cadEngineResult?.detected?.dimensions) return [];
    return cadEngineResult.detected.dimensions.map((d: any, i: number) => ({
      text: d.raw || d.tag || `dim_${i}`,
      value_cm: d.value_cm || 0,
      is_diameter: (d.tag || '').toLowerCase().includes('dia') || (d.raw || '').includes('%'),
      source: d.source || (cadEngineResult.accuracy_pipeline?.associations?.associations?.[i]?.source || 'ocr_confirmed'),
      confidence: d.confidence || cadEngineResult.accuracy_pipeline?.associations?.associations?.[i]?.confidence || 0.5,
      evidence: cadEngineResult.accuracy_pipeline?.associations?.associations?.[i]?.evidence || [],
    }));
  }, [cadEngineResult]);

  /** Read accumulated line role corrections from sessionStorage so they survive
   *  across correction requests (instead of being overwritten with '[]'). */
  function getAccumulatedRoleCorrections(): string {
    try {
      const raw = sessionStorage.getItem('cad_line_role_corrections');
      if (!raw) return '[]';
      const pairs: [string, string][] = JSON.parse(raw);
      return JSON.stringify(pairs.map(([lineId, correctedRole]) => ({
        session_id: cadEngineResult?.job_id || '',
        line_id: lineId,
        original_role: '',
        corrected_role: correctedRole,
        is_locked: true,
      })));
    } catch {
      return '[]';
    }
  }

  const handleCorrectValue = useCallback(async (text: string, newValue: number) => {
    if (!cadEngineResult?.job_id) return;
    try {
      const res = await fetch('/py-api/corrections/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          session_id: cadEngineResult.job_id,
          dimension_corrections: JSON.stringify([{
            session_id: cadEngineResult.job_id,
            ocr_text: text,
            original_value_cm: confidenceDims.find(d => d.text === text)?.value_cm || 0,
            corrected_value_cm: newValue,
            is_locked: true,
          }]),
          line_role_corrections: getAccumulatedRoleCorrections(),
        }),
      });
      if (res.ok) {
        setCorrectionCount(c => c + 1);
        setCurrentDims(prev => ({ ...prev, [text]: newValue }));
      }
    } catch (err) {
      console.error('[Correction] Failed:', err);
    }
  }, [cadEngineResult, confidenceDims]);

  const handleLockDimension = useCallback(async (text: string) => {
    if (!cadEngineResult?.job_id) return;
    try {
      const dim = confidenceDims.find(d => d.text === text);
      if (!dim) return;
      await fetch('/py-api/corrections/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          session_id: cadEngineResult.job_id,
          dimension_corrections: JSON.stringify([{
            session_id: cadEngineResult.job_id,
            ocr_text: text,
            original_value_cm: dim.value_cm,
            corrected_value_cm: dim.value_cm,
            is_locked: true,
          }]),
          line_role_corrections: getAccumulatedRoleCorrections(),
        }),
      });
      setCorrectionCount(c => c + 1);
    } catch (err) {
      console.error('[Lock] Failed:', err);
    }
  }, [cadEngineResult, confidenceDims]);

  const isProcessing = processState === 'processing';
  const allPrimitives = cadDoc?.views?.flatMap(v => v.primitives || []) || [];
  const dims = cadEngineResult?.detected?.dimensions || [];
  const detectedFurniture = cadEngineResult?.furniture ?? null;

  return (
    <ErrorBoundary>
    <div className="h-screen flex flex-col bg-slate-50 font-sans">
      <TechStackModal isOpen={isTechModalOpen} onClose={() => setIsTechModalOpen(false)} />

      {updateAvailable && (
        <div className="bg-amber-500 text-white text-sm px-4 py-2 flex items-center justify-center gap-3 flex-shrink-0 z-30">
          <span>A new version of the app is available.</span>
          <button onClick={() => window.location.reload()} className="px-3 py-1 bg-white text-amber-700 rounded font-bold hover:bg-amber-50">Reload</button>
        </div>
      )}

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
          <div className="flex items-center bg-slate-100 rounded-xl p-0.5 border border-slate-200">
            <button onClick={() => setEngineMode('opencv')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${engineMode === 'opencv' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>
              <Cpu className="w-3.5 h-3.5" /><span>OpenCV</span>
            </button>
            <button onClick={() => setEngineMode('hybrid')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${engineMode === 'hybrid' ? 'bg-white text-purple-600 shadow-sm ring-2 ring-purple-300' : 'text-slate-500 hover:text-slate-700'}`}>
              <Bot className="w-3.5 h-3.5" /><span>Hybrid</span>
            </button>
            <button onClick={() => setEngineMode('smart')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${engineMode === 'smart' ? 'bg-white text-emerald-600 shadow-sm ring-2 ring-emerald-300' : 'text-slate-500 hover:text-slate-700'}`}>
              <Sparkles className="w-3.5 h-3.5" /><span>Smart</span>
            </button>
            <button onClick={() => setEngineMode('ai')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${engineMode === 'ai' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>
              <Bot className="w-3.5 h-3.5" /><span>AI</span>
            </button>
            <button onClick={() => setEngineMode('pipeline')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${engineMode === 'pipeline' ? 'bg-white text-emerald-600 shadow-sm ring-2 ring-emerald-300' : 'text-slate-500 hover:text-slate-700'}`}>
              <Play className="w-3.5 h-3.5" /><span>Pipeline</span>
            </button>
          </div>
          {engineHealthy !== null && engineMode !== 'ai' && (
            <span className={`flex items-center space-x-1 text-xs px-2 py-1 rounded-full border ${engineHealthy ? 'text-emerald-600 bg-emerald-50 border-emerald-200' : 'text-amber-600 bg-amber-50 border-amber-200'}`}>
              <Cpu className="w-3 h-3" /><span>{engineHealthy ? 'Engine Online' : 'Engine Offline'}</span>
            </span>
          )}
          <button onClick={() => setIsTechModalOpen(true)}
            className="flex items-center space-x-1.5 text-sm font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 px-3 py-1.5 rounded-full transition-colors border border-indigo-100">
            <Info className="w-4 h-4" /><span>Info</span>
          </button>
        </div>
      </header>

      {/* NAV */}
      <NavBar activeTab={currentTab} onTabChange={setCurrentTab} />

      {/* MAIN */}
      <main className="flex-1 flex overflow-hidden">
        {currentTab === 'templates' ? (
          <TemplatesPage />
        ) : currentTab === 'calibration' ? (
          <CalibrationPage />
        ) : currentTab === 'analytics' ? (
          <div className="flex-1 overflow-y-auto bg-gradient-to-b from-slate-50 to-slate-100">
            <AnalyticsPage />
          </div>
        ) : currentTab === 'improvements' ? (
          <div className="flex-1 overflow-y-auto bg-gradient-to-b from-slate-50 to-slate-100">
            <ImprovementsPage />
          </div>
        ) : currentTab === 'resources' ? (
          <div className="flex-1 overflow-y-auto bg-gradient-to-b from-slate-50 to-slate-100">
            <ResourcesPage />
          </div>
        ) : currentTab === 'workflow' ? (
          <div className="flex-1 overflow-y-auto">
            <WorkflowGuide />
          </div>
        ) : currentTab === 'crawl' ? (
          <div className="flex-1 flex flex-col items-center justify-center p-6 bg-gradient-to-b from-slate-50 to-slate-100 overflow-y-auto">
            <div className="w-full max-w-xl mb-4">
              <CrawlInput />
            </div>
            <div className="w-full max-w-xl mt-2 p-4 bg-white rounded-2xl shadow-sm border border-slate-200">
              <p className="text-xs text-slate-400 text-center">
                Or use the <strong>Upload Drawing</strong> tab to upload a photo directly.
              </p>
            </div>
          </div>
        ) : processState === 'idle' ? (
          // === UPLOAD SCREEN ===
          <div className="flex-1 flex flex-col items-center justify-center p-6 bg-gradient-to-b from-slate-50 to-slate-100 overflow-y-auto">
            <div className="max-w-2xl text-center mb-8">
              <h2 className="text-4xl font-extrabold text-slate-800 mb-4 tracking-tight">Furniture Drawing → Scaled DXF</h2>
              <p className="text-slate-600 text-lg leading-relaxed mb-4">Upload a furniture drawing with written dimensions.</p>
              <p className="text-slate-500 text-sm">Supports PNG, JPEG, PDF &bull; Template-based reconstruction</p>
            </div>

            <div className="w-full max-w-xl mb-6 p-5 bg-white rounded-2xl shadow-sm border border-slate-200">
              <h3 className="text-sm font-bold text-slate-700 mb-3 flex items-center"><Ruler className="w-4 h-4 mr-2" />Optional: Known Dimensions</h3>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Width (cm)</label>
                  <input type="number" value={realWidthCm} onChange={e => setRealWidthCm(e.target.value)} placeholder="e.g. 80" className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Height (cm)</label>
                  <input type="number" value={realHeightCm} onChange={e => setRealHeightCm(e.target.value)} placeholder="e.g. 70" className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500" />
                </div>
              </div>
              <div className="mb-4">
                <label className="block text-xs font-medium text-slate-500 mb-1">Style Preset</label>
                <select value={selectedPreset} onChange={e => setSelectedPreset(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500">
                  <option value="">None — use defaults</option>
                  <option value="Modern_Round_Table">Modern Round Table (oak + brass)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Furniture Type</label>
                <select value={furnitureType} onChange={e => setFurnitureType(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500">
                  {FURNITURE_TYPES.map(ft => (<option key={ft.value} value={ft.value}>{ft.label}</option>))}
                </select>
              </div>
            </div>

            {/* Pipeline Upload */}
            {engineMode === 'pipeline' ? (
              <div className="w-full max-w-xl">
                <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-4">
                  <h3 className="text-sm font-bold text-slate-700 mb-2 flex items-center">
                    <Play className="w-4 h-4 mr-2 text-emerald-500" />Pipeline Mode
                  </h3>
                  <p className="text-xs text-slate-500 mb-4">Upload a photo for the full pipeline: Cloud Vision → CAD Kernel → DXF/PDF.</p>
                  <PipelineUpload
                    onPipelineComplete={(r) => { setPipelineResult(r); setProcessState('complete'); }}
                    digitizeResult={cadEngineResult ?? undefined}
                    furnitureLabel={cadEngineResult?.furniture?.type ? getFurnitureLabel(cadEngineResult.furniture.type) : undefined}
                  />
                </div>
              </div>
            ) : (
              <>
                <div
                  className="w-full max-w-xl p-12 border-2 border-dashed border-indigo-300 rounded-3xl bg-white hover:border-indigo-500 hover:bg-indigo-50/50 transition-all duration-300 cursor-pointer flex flex-col items-center text-center shadow-xl shadow-indigo-100/20 group"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input type="file" ref={fileInputRef} onChange={handleFileUpload} accept="image/png,image/jpeg,image/jpg,image/webp,application/pdf" className="hidden" />
                  <div className="bg-indigo-100 p-5 rounded-full mb-6 group-hover:scale-110 transition-transform duration-300"><UploadCloud className="w-12 h-12 text-indigo-600" /></div>
                  <h3 className="text-2xl font-bold text-slate-800 mb-2">Upload Drawing</h3>
                  <p className="text-slate-500 font-medium">PNG, JPEG, PDF &bull; Click to browse</p>
                  {engineMode === 'opencv' && !engineHealthy && (<p className="text-amber-500 text-xs mt-2">⚠️ Python engine not detected</p>)}
                </div>
                {pendingFile ? (
                  <div className="mt-6 w-full max-w-xl flex flex-col items-center">
                    <div className="flex items-center space-x-2 bg-emerald-50 border border-emerald-200 text-emerald-700 px-4 py-2 rounded-full text-sm font-semibold mb-4">
                      <CheckCircle2 className="w-4 h-4" /><span className="truncate max-w-xs">{pendingFile.name}</span>
                    </div>
                    {imageSrc && (<img src={imageSrc} alt="Preview" className="max-h-48 max-w-full rounded-xl shadow-md border border-slate-200 mb-4 object-contain" />)}
                    <button onClick={handleStart} className="flex items-center space-x-3 px-10 py-4 bg-indigo-600 text-white rounded-2xl text-lg font-bold hover:bg-indigo-700 active:scale-95 transition-all shadow-xl shadow-indigo-200 ring-4 ring-indigo-100">
                      <Play className="w-6 h-6" /><span>Start Digitizing</span>
                    </button>
                    <button onClick={() => { setPendingFile(null); setImageSrc(null); if (fileInputRef.current) fileInputRef.current.value = ''; }} className="mt-2 text-xs text-slate-400 hover:text-slate-600 transition-colors">✕ Cancel selection</button>
                  </div>
                ) : null}
              </>
            )}

            {/* ChatBox + BrainStats */}
            <div className="mt-8 w-full max-w-md">
              <div className="p-4 border border-slate-200 rounded-xl bg-white"><BrainStats /></div>
              <div className="mt-3 p-4 border border-slate-200 rounded-xl bg-white">
                <ChatBox onRenderRequest={handleChatRender} />
              </div>
            </div>
          </div>
        ) : (
          // === RESULT SCREEN ===
          <div className="flex-1 flex w-full h-full">
            <div className="w-80 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col shadow-[4px_0_24px_rgba(0,0,0,0.02)] z-10 overflow-hidden">
              <div className="p-5 border-b border-slate-100 bg-slate-50/80">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center"><Shapes className="w-4 h-4 mr-1.5" /> Status</h3>
                {isProcessing ? (
                  <div className="flex items-center space-x-3 text-indigo-700 bg-indigo-100/50 p-3 rounded-xl border border-indigo-200 shadow-sm">
                    <Loader2 className="w-5 h-5 animate-spin flex-shrink-0" /><span className="text-sm font-semibold">{status}</span>
                  </div>
                ) : error ? (
                  <div className="flex flex-col space-y-1">
                    <div className="flex items-start space-x-2 text-red-700 bg-red-50 p-3 rounded-xl border border-red-200 shadow-sm">
                      <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" /><span className="text-sm font-semibold">{error}</span>
                    </div>
                    <button onClick={() => { setImageSrc(null); setCadEngineResult(null); setCadDoc(null); setProcessState('idle'); setError(null); setMode('idle'); setPendingFile(null); }} className="text-xs text-indigo-600 underline text-left p-1 hover:text-indigo-800">← Try again</button>
                  </div>
                ) : (
                  <div className="flex items-center space-x-2 text-emerald-700 bg-emerald-50 p-3 rounded-xl border border-emerald-200 shadow-sm">
                    <CheckCircle2 className="w-5 h-5 flex-shrink-0" /><span className="text-sm font-semibold">Complete</span>
                  </div>
                )}
              </div>

              <div className="flex-1 overflow-y-auto">
                {/* PIPELINE RESULT */}
                {pipelineResult && !isProcessing && (
                  <div className="p-5 space-y-4">
                    <PipelineProgress result={pipelineResult} />
                    {pipelineResult.outputs?.dxf_url && (
                      <DXFPreview
                        dxfUrl={pipelineResult.outputs.dxf_url}
                        svgUrl={pipelineResult.outputs.dxf_url?.replace('.dxf', '.svg')}
                        viewUrl={pipelineResult.outputs.dxf_url?.replace('/download/', '/view/')}
                      />
                    )}
                    <ReviewPanel result={pipelineResult} phase3Result={cadEngineResult?.phase3 ?? null} />
                  </div>
                )}

                {/* RESULTS - OpenCV Engine */}
                {cadEngineResult && !isProcessing && (
                  <div className="p-5 space-y-4">
                    <div className="text-xs text-slate-500 bg-slate-50 p-2 rounded-lg flex items-center space-x-2">
                      <FileText className="w-3.5 h-3.5" /><span className="truncate">{fileName}</span>
                    </div>
                    {detectedFurniture && (
                      <div>
                        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Furniture</h3>
                        <div className="bg-purple-50 p-3 rounded-xl border border-purple-200">
                          <div className="flex justify-between">
                            <span className="font-bold text-sm text-purple-700">{getFurnitureLabel(detectedFurniture.type)}</span>
                            <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${detectedFurniture.confidence >= 0.8 ? 'bg-emerald-100 text-emerald-700' : detectedFurniture.confidence >= 0.5 ? 'bg-amber-100 text-amber-700' : 'bg-slate-200 text-slate-600'}`}>
                              {getFurnitureConfidenceLabel(detectedFurniture.confidence)}
                            </span>
                          </div>
                          <div className="text-xs text-slate-500 mt-1">Confidence: {Math.round(detectedFurniture.confidence * 100)}%</div>
                        </div>
                      </div>
                    )}
                    {cadEngineResult.dxf_file && (
                      <div className="border-2 border-indigo-200 bg-indigo-50/40 rounded-xl p-3">
                        <h3 className="text-xs font-bold text-indigo-600 uppercase tracking-wider mb-2 flex items-center">
                          <Settings className="w-3.5 h-3.5 mr-1.5" /> Edit Drawing
                        </h3>
                        <SliderPanel dxfFile={cadEngineResult.dxf_file} initialDims={currentDims} furnitureType={cadEngineResult?.furniture?.type}
                          highlightKey={highlightedSliderKey} componentSchema={cadEngineResult?.component_schema}
                          highlightComponent={highlightedComponent}
                          onAdjusted={(dims, svgUrl) => { setCurrentDims(dims); setSvgPreviewUrl(svgUrl); setPreviewSvgVersion(v => v + 1); }} />
                      </div>
                    )}

                    <div>
                      <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2"><Layers className="w-3 h-3 inline mr-1" /> Detected</h3>
                      <div className="grid grid-cols-2 gap-2">
                        <div className="bg-slate-50 p-2 rounded-lg text-center"><div className="text-lg font-bold text-indigo-600">{cadEngineResult.detected?.lines ?? 0}</div><div className="text-xs text-slate-500">Lines</div></div>
                        <div className="bg-slate-50 p-2 rounded-lg text-center"><div className="text-lg font-bold text-indigo-600">{cadEngineResult.detected?.circles ?? 0}</div><div className="text-xs text-slate-500">Circles</div></div>
                        <div className="bg-slate-50 p-2 rounded-lg text-center"><div className="text-lg font-bold text-indigo-600">{cadEngineResult.detected?.rectangles ?? 0}</div><div className="text-xs text-slate-500">Rectangles</div></div>
                        <div className="bg-slate-50 p-2 rounded-lg text-center"><div className="text-lg font-bold text-indigo-600">{dims.length}</div><div className="text-xs text-slate-500">Dimensions</div></div>
                      </div>
                    </div>

                    {confidenceDims.length > 0 && (
                      <div className="border-t border-slate-100 pt-3 mt-3">
                        <button onClick={() => setShowConfidencePanel(!showConfidencePanel)} className="w-full flex items-center justify-between px-3 py-2 bg-white rounded-xl border border-slate-200 hover:border-indigo-300 transition-colors">
                          <span className="text-xs font-bold text-slate-600 flex items-center"><Shield className="w-3.5 h-3.5 mr-1.5 text-indigo-500" />Accuracy & Confidence{correctionCount > 0 && <span className="ml-2 text-[10px] bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded-full font-bold">{correctionCount}</span>}</span>
                          <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${showConfidencePanel ? 'rotate-180' : ''}`} />
                        </button>
                        {showConfidencePanel && (
                          <div className="mt-2 max-h-96 overflow-y-auto">
                            <ConfidencePanel dimensions={confidenceDims} associations={cadEngineResult?.accuracy_pipeline?.associations?.associations}
                              lineRoles={cadEngineResult?.accuracy_pipeline?.line_roles} onCorrectValue={handleCorrectValue}
                              onLockDimension={handleLockDimension} onCorrectLineRole={(lineId, newRole) => {
                                if (!cadEngineResult?.job_id) return;
                                fetch('/py-api/corrections/submit', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ session_id: cadEngineResult.job_id, dimension_corrections: '[]', line_role_corrections: JSON.stringify([{ session_id: cadEngineResult.job_id, line_id: lineId, original_role: '', corrected_role: newRole, is_locked: true }]), }) }).catch(console.error);
                              }} />
                          </div>
                        )}
                      </div>
                    )}

                    {(cadEngineResult.warnings || []).length > 0 && (
                      <div><h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Notes</h3>
                        <ul className="text-xs space-y-1">{(cadEngineResult.warnings || []).map((w, i) => (<li key={i} className="text-amber-700 bg-amber-50 p-2 rounded-lg">• {w}</li>))}</ul>
                      </div>
                    )}
                  </div>
                )}

                {/* RESULTS - AI Engine */}
                {cadDoc && !isProcessing && (
                  <div className="p-5 space-y-4">
                    {verification && (
                      <div>
                        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Quality</h3>
                        <div className={`p-3 rounded-xl border text-sm ${verification.approved ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}`}>
                          <div className="flex justify-between mb-1"><span className="font-bold">{verification.approved ? '✅ Approved' : '⚠️ Needs Review'}</span><span className="font-black">{verification.score}/100</span></div>
                          <ul className="text-xs space-y-1">{verification.feedback.map((fb, i) => <li key={i} className="text-slate-600">• {fb}</li>)}</ul>
                        </div>
                      </div>
                    )}
                    <div>
                      <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Views</h3>
                      {cadDoc.views.map((v, i) => (<div key={i} className="text-xs bg-slate-50 p-2 rounded-lg mb-1"><span className="font-semibold">{v.name}</span><span className="text-slate-500 ml-2">({v.primitives.length} primitives)</span></div>))}
                    </div>
                  </div>
                )}

                <div className="p-4 border-t border-slate-200"><BrainStats /></div>
                {((cadEngineResult?.smart_workflow as any)?.confirmation_questions?.length > 0
                  || (cadEngineResult as any)?.uncertainty_questions?.length > 0) && cadEngineResult && (
                  <div className="px-4 border-t border-slate-200">
                    <SmartConfirmations
                      questions={(cadEngineResult as any).smart_workflow.confirmation_questions || []}
                      uncertaintyQuestions={(cadEngineResult as any).uncertainty_questions || []}
                      disabled={isProcessing}
                      onApply={async (answers) => {
                        if (!pendingFile && !fileInputRef.current?.files?.[0]) return;
                        const file = pendingFile || fileInputRef.current.files[0];
                        if (!file) return;
                        const selectedType = (answers as any).furniture_type || furnitureType;
                        setFurnitureType(selectedType);
                        setProcessState("processing");
                        setStatus("Regenerating DXF with confirmed answers...");
                        try {
                          const { digitizeSmartAuto } = await import("./services/cadEngine");
                          const result = await digitizeSmartAuto(file, {
                            realWidthCm: realWidthCm ? parseFloat(realWidthCm) : undefined,
                            realHeightCm: realHeightCm ? parseFloat(realHeightCm) : undefined,
                            furnitureType: selectedType || undefined,
                            answers: answers as Record<string, string>,
                          });
                          setCadEngineResult(result);
                          setProcessState("complete");
                          setStatus("DXF regenerated with confirmed answers.");
                        } catch (err: any) {
                          setError(`❌ ${err?.message || "Regeneration failed"}`);
                          setProcessState("error");
                        }
                      }}
                    />
                  </div>
                )}
                {!isProcessing && (
                  <div className="p-4 border-t border-slate-200">
                    <ChatBox sessionId={cadEngineResult?.job_id} imageId={cadEngineResult?.job_id} dxfFile={cadEngineResult?.dxf_file} onRenderRequest={handleChatRender} />
                  </div>
                )}
              </div>

              {/* EXPORT */}
              {((cadEngineResult || cadDoc) && !isProcessing) && (
                <div className="p-5 bg-white mt-auto border-t border-slate-200">
                  <button onClick={handleExportDXF} className="w-full flex items-center justify-center space-x-2 px-4 py-3.5 bg-slate-900 text-white rounded-xl text-sm font-bold hover:bg-indigo-600 transition-all shadow-lg">
                    <Download className="w-5 h-5" /><span>{cadEngineResult ? 'Download DXF (Scaled)' : 'Export DXF'}</span>
                  </button>
                  <button onClick={() => { setImageSrc(null); setCadEngineResult(null); setCadDoc(null); setProcessState('idle'); setPipelineResult(null); }} className="w-full text-xs text-slate-500 py-2 mt-2 hover:text-slate-700 transition-colors">← Upload another drawing</button>
                </div>
              )}
            </div>

            {/* CANVAS / PREVIEW */}
            <div className="flex-1 relative overflow-auto bg-slate-200/50">
              {cadEngineResult && (
                <div className="p-6">
                  <div className="bg-white rounded-2xl shadow-lg p-4 mb-4">
                    <h3 className="text-sm font-bold text-slate-700 mb-3 flex items-center"><Image className="w-4 h-4 mr-2" />Uploaded Drawing</h3>
                    {imageSrc && <img src={imageSrc} alt="Uploaded drawing" className="max-w-full max-h-[500px] mx-auto rounded-lg" />}
                  </div>
                  <div className="bg-white rounded-2xl shadow-lg p-4">
                    <h3 className="text-sm font-bold text-slate-700 mb-2 flex items-center"><Settings className="w-4 h-4 mr-2" />Result Summary</h3>
                    <div className="text-sm text-slate-600 space-y-1">
                      <p>🏷️ Furniture: <strong>{detectedFurniture ? getFurnitureLabel(detectedFurniture.type || '') : 'N/A'}</strong></p>
                      <p>📐 Lines: <strong>{cadEngineResult.detected?.lines ?? 0}</strong> | Circles: <strong>{cadEngineResult.detected?.circles ?? 0}</strong></p>
                      <p>💾 DXF: <strong>{cadEngineResult.dxf_file}</strong></p>
                    </div>
                    {cadEngineResult.dxf_file && (
                      <div className="mt-3 space-y-2">
                        {cadEngineResult.preview_svg ? (
                          <InteractiveSvgPreview src={`${getSvgPreviewUrl(cadEngineResult.preview_svg)}?v=${previewSvgVersion}`} alt="DXF Preview" className="w-full rounded-lg border border-slate-200 [&_[data-component]:hover]:fill-indigo-500/10" onPartClick={handlePartClick} />
                        ) : (
                          <img src={getPreviewUrl(cadEngineResult.dxf_file)} alt="DXF Preview" className="w-full rounded-lg border border-slate-200" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
                        )}
                        <div className="flex gap-2">
                          <a href={getPdfUrl(cadEngineResult.dxf_file)} target="_blank" className="flex-1 text-center bg-red-600 text-white text-xs py-2 rounded-lg hover:bg-red-700 font-medium">View PDF</a>
                          <a href={getPreviewUrl(cadEngineResult.dxf_file)} target="_blank" className="flex-1 text-center bg-blue-600 text-white text-xs py-2 rounded-lg hover:bg-blue-700 font-medium">Full Preview</a>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <canvas ref={canvasRef} className="block mx-auto shadow-2xl" style={{ maxWidth: '100%', height: 'auto' }} />

              {isProcessing && (
                <div className="absolute inset-0 bg-slate-900/30 backdrop-blur-md flex items-center justify-center z-50">
                  <div className="bg-white p-8 rounded-3xl shadow-2xl flex flex-col items-center max-w-sm text-center border border-slate-100">
                    <div className="relative w-20 h-20 mb-6">
                      <div className="absolute inset-0 border-4 border-indigo-100 rounded-full"></div>
                      <div className="absolute inset-0 border-4 border-indigo-600 rounded-full border-t-transparent animate-spin"></div>
                      {engineMode === 'opencv' ? <Cpu className="absolute inset-0 m-auto w-8 h-8 text-indigo-600" /> : <Bot className="absolute inset-0 m-auto w-8 h-8 text-indigo-600" />}
                    </div>
                    <h3 className="text-xl font-bold text-slate-800 mb-2">{engineMode === 'opencv' ? 'Processing Drawing' : 'AI Analyzing'}</h3>
                    <p className="text-sm text-slate-500">{status}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
    </ErrorBoundary>
  );
};

export default App;
