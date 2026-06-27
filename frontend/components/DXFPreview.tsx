import React, { useState } from 'react';
import { Download, ExternalLink, Image, FileText } from 'lucide-react';

interface DXFPreviewProps {
  dxfUrl?: string;
  svgUrl?: string;
  pdfUrl?: string;
  viewUrl?: string;
  fileName?: string;
  showTitle?: boolean;
  className?: string;
}

const DXFPreview: React.FC<DXFPreviewProps> = ({
  dxfUrl, svgUrl, pdfUrl, viewUrl, fileName, showTitle = true, className = ''
}) => {
  const [imgError, setImgError] = useState(false);
  const base = import.meta.env.VITE_CAD_ENGINE_URL || '';

  const resolveUrl = (path: string) => {
    if (!path) return '';
    const proxyPath = path.replace('/api/', '/py-api/');
    if (base.startsWith('http')) return `${base}${path}`;
    return `${window.location.origin}${proxyPath}`;
  };

  const handleDownload = () => {
    if (!dxfUrl) return;
    fetch(resolveUrl(dxfUrl))
      .then(res => res.blob())
      .then(blob => {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = fileName || 'drawing.dxf';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(a.href);
      })
      .catch(console.error);
  };

  return (
    <div className={`space-y-3 ${className}`}>
      {showTitle && (
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center">
          <Image className="w-3.5 h-3.5 mr-1.5" /> Drawing Preview
        </h3>
      )}

      {/* SVG Preview */}
      {svgUrl && !imgError ? (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
          <img
            src={`${resolveUrl(svgUrl)}?v=${Date.now()}`}
            alt="Drawing preview"
            className="w-full object-contain"
            onError={() => setImgError(true)}
          />
        </div>
      ) : (
        <div className="bg-slate-50 rounded-xl border border-slate-200 p-8 text-center text-slate-400">
          <Image className="w-8 h-8 mx-auto mb-2" />
          <p className="text-xs">No preview available</p>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2 flex-wrap">
        {dxfUrl && (
          <button onClick={handleDownload}
            className="flex-1 flex items-center justify-center space-x-1.5 px-3 py-2 bg-slate-900 text-white rounded-lg text-xs font-bold hover:bg-indigo-600 transition-all">
            <Download className="w-3.5 h-3.5" />
            <span>DXF</span>
          </button>
        )}
        {pdfUrl && (
          <a href={resolveUrl(pdfUrl)} target="_blank"
            className="flex-1 flex items-center justify-center space-x-1.5 px-3 py-2 bg-red-600 text-white rounded-lg text-xs font-bold hover:bg-red-700 transition-all">
            <FileText className="w-3.5 h-3.5" />
            <span>PDF</span>
          </a>
        )}
        {viewUrl && (
          <a href={resolveUrl(viewUrl)} target="_blank"
            className="flex-1 flex items-center justify-center space-x-1.5 px-3 py-2 bg-purple-600 text-white rounded-lg text-xs font-bold hover:bg-purple-700 transition-all">
            <ExternalLink className="w-3.5 h-3.5" />
            <span>View</span>
          </a>
        )}
      </div>
    </div>
  );
};

export default DXFPreview;
