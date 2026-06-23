import React from 'react';
import { X, Code2, CheckCircle2, XCircle, Sparkles } from 'lucide-react';

interface TechStackModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const TechStackModal: React.FC<TechStackModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-2 text-indigo-600">
            <Sparkles className="w-5 h-5" />
            <h2 className="text-lg font-bold text-slate-800">Application Tech Stack</h2>
          </div>
          <button 
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-200 rounded-full transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="p-6 overflow-y-auto">
          <p className="text-slate-600 mb-6 leading-relaxed">
            This application uses <span className="font-mono text-xs bg-slate-100 px-1.5 py-0.5 rounded">Gemini API</span> for all AI processing. Simply add your API key in a <span className="font-mono text-xs bg-slate-100 px-1.5 py-0.5 rounded">.env</span> file — no Google Cloud project or backend setup needed.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-5">
              <h3 className="text-emerald-800 font-semibold mb-4 flex items-center">
                <CheckCircle2 className="w-4 h-4 mr-2 text-emerald-600" />
                Current Stack (Used Here)
              </h3>
              <ul className="space-y-3 text-sm text-emerald-900">
                <li className="flex items-start">
                  <span className="font-bold mr-2">•</span>
                  <span><strong>React 18 & TypeScript:</strong> Pure frontend SPA running entirely in your browser.</span>
                </li>
                <li className="flex items-start">
                  <span className="font-bold mr-2">•</span>
                  <span><strong>Gemini API (gemini-2.5-flash):</strong> Handles spatial reasoning, scale detection, polyline tracing, and OCR — all in one multimodal API call. No Vertex AI / Google Cloud project needed, just an API key.</span>
                </li>
                <li className="flex items-start">
                  <span className="font-bold mr-2">•</span>
                  <span><strong>@google/genai SDK:</strong> Client-side library that calls Gemini API directly from the browser.</span>
                </li>
                <li className="flex items-start">
                  <span className="font-bold mr-2">•</span>
                  <span><strong>Tailwind CSS:</strong> For rapid, beautiful UI styling.</span>
                </li>
                <li className="flex items-start">
                  <span className="font-bold mr-2">•</span>
                  <span><strong>Custom DXF Generator:</strong> Generates the AC1009 DXF format directly in TypeScript using browser Blobs.</span>
                </li>
                <li className="flex items-start">
                  <span className="font-bold mr-2">•</span>
                  <span><strong>Browser Canvas API:</strong> For manual snap drawing and local line detection.</span>
                </li>
              </ul>
            </div>

            <div className="bg-slate-50 border border-slate-200 rounded-xl p-5">
              <h3 className="text-slate-700 font-semibold mb-4 flex items-center">
                <XCircle className="w-4 h-4 mr-2 text-slate-400" />
                What We Don't Need
              </h3>
              <ul className="space-y-3 text-sm text-slate-600">
                <li className="flex items-start">
                  <span className="font-bold mr-2 text-slate-400">•</span>
                  <span><strong>No backend server needed:</strong> Gemini SDK calls the API directly from the browser.</span>
                </li>
                <li className="flex items-start">
                  <span className="font-bold mr-2 text-slate-400">•</span>
                  <span><strong>No Google Cloud project:</strong> Just a free Gemini API key from aistudio.google.com.</span>
                </li>
                <li className="flex items-start">
                  <span className="font-bold mr-2 text-slate-400">•</span>
                  <span><strong>No Ollama:</strong> Uses Gemini cloud API instead of local models.</span>
                </li>
                <li className="flex items-start">
                  <span className="font-bold mr-2 text-slate-400">•</span>
                  <span><strong>No Python / OpenCV:</strong> All computer vision is handled by Gemini's multimodal AI.</span>
                </li>
                <li className="flex items-start">
                  <span className="font-bold mr-2 text-slate-400">•</span>
                  <span><strong>No DXF libraries:</strong> We generate DXF natively in TypeScript.</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
        
        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50 flex justify-end">
          <button 
            onClick={onClose}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
          >
            Got it!
          </button>
        </div>
      </div>
    </div>
  );
};

export default TechStackModal;
