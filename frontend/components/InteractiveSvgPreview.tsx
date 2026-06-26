import React, { useEffect, useRef, useState } from 'react';

interface InteractiveSvgPreviewProps {
  src: string;
  onPartClick?: (component: string) => void;
  className?: string;
  alt?: string;
}

/**
 * Renders a backend-generated drawing SVG inline (instead of <img>) so
 * individual named parts (data-component, see svg_exporter.py) can be
 * clicked. Falls back to a plain <img> if the SVG can't be fetched/parsed
 * (e.g. CORS, network error) so the preview never just disappears.
 */
const InteractiveSvgPreview: React.FC<InteractiveSvgPreviewProps> = ({ src, onPartClick, className = '', alt }) => {
  const [svgMarkup, setSvgMarkup] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    setSvgMarkup(null);
    fetch(src)
      .then(resp => {
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.text();
      })
      .then(text => {
        if (!cancelled) setSvgMarkup(text);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => { cancelled = true; };
  }, [src]);

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.target as Element;
    const part = target.closest('[data-component]');
    if (part && onPartClick) {
      onPartClick(part.getAttribute('data-component') || '');
    }
  };

  if (failed) {
    return <img src={src} alt={alt} className={className} onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />;
  }

  if (!svgMarkup) {
    return <div className={`${className} animate-pulse bg-slate-100 rounded-lg`} style={{ minHeight: 200 }} />;
  }

  return (
    <div
      ref={containerRef}
      className={className}
      onClick={handleClick}
      dangerouslySetInnerHTML={{ __html: svgMarkup }}
    />
  );
};

export default InteractiveSvgPreview;
