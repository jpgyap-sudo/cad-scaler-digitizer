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
 * clicked. Falls back to a plain <img> if the SVG can't be fetched/parsed.
 * 
 * Supports dynamic tab selectors to toggle between Top, Front, Side, and All views,
 * automatically recalculating viewBox coordinates to zoom in on target views.
 */
const InteractiveSvgPreview: React.FC<InteractiveSvgPreviewProps> = ({ src, onPartClick, className = '', alt }) => {
  const [svgMarkup, setSvgMarkup] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const [availableViews, setAvailableViews] = useState<string[]>([]);
  const [activeView, setActiveView] = useState<string>('all');
  const originalViewBoxRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    setSvgMarkup(null);
    setAvailableViews([]);
    setActiveView('all');
    originalViewBoxRef.current = null;

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

  // Parse available views from DOM after SVG is injected
  useEffect(() => {
    if (!svgMarkup || !containerRef.current) return;

    const timer = setTimeout(() => {
      const svg = containerRef.current?.querySelector('svg');
      if (svg) {
        // Capture original viewBox
        const origBox = svg.getAttribute('viewBox');
        if (origBox) {
          originalViewBoxRef.current = origBox;
        }

        const views = svg.querySelectorAll('.cad-view');
        const found: string[] = [];
        views.forEach(v => {
          const name = v.getAttribute('data-view');
          if (name && !found.includes(name)) {
            found.push(name);
          }
        });
        setAvailableViews(found);
      }
    }, 50);

    return () => clearTimeout(timer);
  }, [svgMarkup]);

  // Apply view filtering and viewBox zooming
  useEffect(() => {
    if (!containerRef.current) return;
    const svg = containerRef.current.querySelector('svg');
    if (!svg) return;

    const views = svg.querySelectorAll('.cad-view') as NodeListOf<SVGGElement>;

    if (activeView === 'all') {
      // Restore all views
      views.forEach(v => {
        v.style.display = '';
        v.style.opacity = '';
      });
      
      // Restore all background and layout elements
      svg.querySelectorAll('rect, line, text').forEach((el: any) => {
        el.style.display = '';
      });

      if (originalViewBoxRef.current) {
        svg.setAttribute('viewBox', originalViewBoxRef.current);
      }
    } else {
      // Hide all other views, show active view
      views.forEach(v => {
        const name = v.getAttribute('data-view');
        if (name === activeView) {
          v.style.display = '';
          v.style.opacity = '';
        } else {
          v.style.display = 'none';
        }
      });

      // Hide sheet border and title block elements for focused view
      const mainGroup = svg.querySelector('g[transform^="translate"]');
      const children = Array.from(svg.children);
      children.forEach((child: any) => {
        if (child !== mainGroup && child.tagName !== 'style' && child.tagName !== 'defs') {
          child.style.display = 'none';
        }
      });

      // Zoom to active view bounding box
      const targetGroup = svg.querySelector(`.cad-view[data-view="${activeView}"]`) as SVGGElement | null;
      if (targetGroup) {
        try {
          const bbox = targetGroup.getBBox();
          
          let dx = 0;
          let dy = 0;
          if (mainGroup) {
            const transform = mainGroup.getAttribute('transform');
            const match = transform?.match(/translate\(([^,)]+)(?:,\s*([^)]+))?\)/);
            if (match) {
              dx = parseFloat(match[1]) || 0;
              dy = parseFloat(match[2]) || 0;
            }
          }

          // Apply padding around the view
          const pad = 30;
          const vx = bbox.x + dx - pad;
          const vy = bbox.y + dy - pad;
          const vw = bbox.width + pad * 2;
          const vh = bbox.height + pad * 2;

          svg.setAttribute('viewBox', `${vx} ${vy} ${vw} ${vh}`);
        } catch (err) {
          console.warn('Failed to calculate view bounding box:', err);
        }
      }
    }
  }, [activeView, svgMarkup]);

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
    return <div className={`${className} animate-pulse bg-slate-100 rounded-lg`} style={{ minHeight: 250 }} />;
  }

  return (
    <div className="space-y-3">
      {availableViews.length > 0 && (
        <div className="flex flex-wrap gap-1 p-1 bg-slate-100/90 rounded-xl border border-slate-200/60 w-fit">
          <button
            onClick={() => setActiveView('all')}
            className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all duration-200 ${
              activeView === 'all'
                ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-500/20'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
            }`}
          >
            All Views
          </button>
          {availableViews.map(view => (
            <button
              key={view}
              onClick={() => setActiveView(view)}
              className={`px-3 py-1 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all duration-200 ${
                activeView === view
                  ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-500/20'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
              }`}
            >
              {view} View
            </button>
          ))}
        </div>
      )}
      <div
        ref={containerRef}
        className={className}
        onClick={handleClick}
        dangerouslySetInnerHTML={{ __html: svgMarkup }}
      />
    </div>
  );
};

export default InteractiveSvgPreview;
