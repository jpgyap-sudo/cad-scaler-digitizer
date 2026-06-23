import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Point, Polyline, AppMode, Calibration } from '../types';

interface CanvasProps {
  imageSrc: string;
  mode: AppMode;
  polylines: Polyline[];
  setPolylines: React.Dispatch<React.SetStateAction<Polyline[]>>;
  calibration: Calibration | null;
  setCalibration: React.Dispatch<React.SetStateAction<Calibration | null>>;
  onCalibrationComplete: () => void;
  selectedPolylineId?: string | null;
  onSelectPolyline?: (id: string | null) => void;
}

/**
 * Genius fix: Use a single <canvas> instead of <img> + <svg> overlay.
 * This eliminates the alignment problem because:
 * - The canvas IS the image — no overlay offset possible
 * - We draw the image + polylines in the same coordinate space
 * - Mouse events are relative to the canvas, not a container
 * - Canvas auto-scales with CSS while keeping internal resolution
 */
const Canvas: React.FC<CanvasProps> = ({ 
  imageSrc, 
  mode, 
  polylines, 
  setPolylines, 
  calibration, 
  setCalibration,
  onCalibrationComplete,
  selectedPolylineId,
  onSelectPolyline
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [currentLine, setCurrentLine] = useState<Point[]>([]);
  const [mousePos, setMousePos] = useState<Point | null>(null);
  const [calibPoints, setCalibPoints] = useState<Point[]>([]);
  const imageDataRef = useRef<ImageData | null>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  // Load image
  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      setImage(img);
      setCanvasSize({ width: img.naturalWidth, height: img.naturalHeight });
    };
    img.src = imageSrc;
  }, [imageSrc]);

  // Draw everything on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !image) return;
    
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Draw image
    ctx.drawImage(image, 0, 0);
    
    // Store pixel data for snap detection
    imageDataRef.current = ctx.getImageData(0, 0, canvas.width, canvas.height);

    // Draw existing polylines
    polylines.forEach(poly => {
      const isSelected = selectedPolylineId === poly.id;
      ctx.beginPath();
      poly.points.forEach((p, i) => {
        if (i === 0) ctx.moveTo(p.x, p.y);
        else ctx.lineTo(p.x, p.y);
      });
      ctx.strokeStyle = isSelected ? '#f59e0b' : '#4f46e5';
      ctx.lineWidth = isSelected ? 4 : 2.5;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.stroke();

      // Draw vertices if selected
      if (isSelected) {
        poly.points.forEach(p => {
          ctx.beginPath();
          ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
          ctx.fillStyle = '#fff';
          ctx.fill();
          ctx.strokeStyle = '#f59e0b';
          ctx.lineWidth = 2;
          ctx.stroke();
        });
      }
    });

    // Draw current drawing line
    if (currentLine.length > 0 && mousePos) {
      ctx.beginPath();
      [...currentLine, mousePos].forEach((p, i) => {
        if (i === 0) ctx.moveTo(p.x, p.y);
        else ctx.lineTo(p.x, p.y);
      });
      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = 2.5;
      ctx.setLineDash([6, 6]);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Draw calibration line
    if (calibration) {
      ctx.beginPath();
      ctx.moveTo(calibration.p1.x, calibration.p1.y);
      ctx.lineTo(calibration.p2.x, calibration.p2.y);
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 3;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(calibration.p1.x, calibration.p1.y, 5, 0, Math.PI * 2);
      ctx.fillStyle = '#10b981';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(calibration.p2.x, calibration.p2.y, 5, 0, Math.PI * 2);
      ctx.fillStyle = '#10b981';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Label
      const mx = (calibration.p1.x + calibration.p2.x) / 2;
      const my = (calibration.p1.y + calibration.p2.y) / 2;
      ctx.fillStyle = '#10b981';
      if (ctx.roundRect) {
        ctx.beginPath();
        ctx.roundRect(mx - 35, my - 28, 70, 24, 6);
        ctx.fill();
      } else {
        ctx.fillRect(mx - 35, my - 28, 70, 24);
      }
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 13px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(`${calibration.realLength}${calibration.unit}`, mx, my - 16);
    }

    // Draw active calibration drawing
    if (calibPoints.length === 1 && mousePos) {
      ctx.beginPath();
      ctx.moveTo(calibPoints[0].x, calibPoints[0].y);
      ctx.lineTo(mousePos.x, mousePos.y);
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 2.5;
      ctx.setLineDash([6, 6]);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }, [image, polylines, currentLine, mousePos, calibration, calibPoints, selectedPolylineId]);

  // Get image-pixel coordinates from mouse event
  const getCanvasCoords = useCallback((e: React.MouseEvent): Point | null => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const raw = {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY
    };
    return (mode === 'draw' || mode === 'calibrate') ? snapToNearestInk(raw) : raw;
  }, [mode]);

  const snapToNearestInk = (p: Point): Point => {
    const img = imageDataRef.current;
    if (!img) return p;
    const radius = 14;
    let best: Point | null = null;
    let bestDist = Infinity;
    const sx = Math.max(0, Math.floor(p.x - radius));
    const ex = Math.min(img.width - 1, Math.ceil(p.x + radius));
    const sy = Math.max(0, Math.floor(p.y - radius));
    const ey = Math.min(img.height - 1, Math.ceil(p.y + radius));
    for (let y = sy; y <= ey; y++) {
      for (let x = sx; x <= ex; x++) {
        const idx = (y * img.width + x) * 4;
        const dark = (img.data[idx] + img.data[idx + 1] + img.data[idx + 2]) / 3 < 175 && img.data[idx + 3] > 10;
        if (!dark) continue;
        const d = Math.hypot(x - p.x, y - p.y);
        if (d < bestDist) { bestDist = d; best = { x, y }; }
      }
    }
    return best || p;
  };

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (mode === 'agent-processing' || mode === 'verifying') return;
    const pos = getCanvasCoords(e);
    setMousePos(pos);
  }, [mode, getCanvasCoords]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (mode === 'agent-processing' || mode === 'verifying') return;
    const pos = getCanvasCoords(e);
    if (!pos) return;

    if (mode === 'idle' && onSelectPolyline) {
      // Check if clicking near a polyline
      let found = false;
      for (const poly of polylines) {
        for (const p of poly.points) {
          if (Math.hypot(p.x - pos.x, p.y - pos.y) < 15) {
            onSelectPolyline(poly.id);
            found = true;
            break;
          }
        }
        if (found) break;
      }
      if (!found) onSelectPolyline(null);
    }

    if (mode === 'calibrate') {
      if (calibPoints.length === 0) {
        setCalibPoints([pos]);
      } else if (calibPoints.length === 1) {
        const newCalibPoints = [calibPoints[0], pos];
        setCalibPoints(newCalibPoints);
        setCalibration(prev => ({
          p1: newCalibPoints[0],
          p2: newCalibPoints[1],
          realLength: prev?.realLength || 1,
          unit: prev?.unit || 'm'
        }));
        onCalibrationComplete();
        setCalibPoints([]);
      }
    } else if (mode === 'draw') {
      setCurrentLine(prev => {
        const next = [...prev];
        let newPos = pos;
        const last = next[next.length - 1];
        if (last && e.shiftKey) {
          newPos = Math.abs(pos.x - last.x) > Math.abs(pos.y - last.y) ? { x: pos.x, y: last.y } : { x: last.x, y: pos.y };
        }
        next.push(newPos);
        return next;
      });
    }
  }, [mode, calibPoints, polylines, onCalibrationComplete, setCalibration, onSelectPolyline, getCanvasCoords]);

  const handleDoubleClick = useCallback(() => {
    if (mode === 'draw' && currentLine.length > 0) {
      setPolylines(prev => [...prev, { id: `manual-poly-${Date.now()}`, points: currentLine }]);
      setCurrentLine([]);
    }
  }, [mode, currentLine, setPolylines]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setCurrentLine([]);
        setCalibPoints([]);
        if (onSelectPolyline) onSelectPolyline(null);
      } else if (e.key === 'Enter' && mode === 'draw' && currentLine.length > 0) {
        setPolylines(prev => [...prev, { id: `manual-poly-${Date.now()}`, points: currentLine }]);
        setCurrentLine([]);
      } else if ((e.key === 'Delete' || e.key === 'Backspace') && selectedPolylineId) {
        setPolylines(prev => prev.filter(p => p.id !== selectedPolylineId));
        if (onSelectPolyline) onSelectPolyline(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [mode, currentLine, setPolylines, selectedPolylineId, onSelectPolyline]);

  const getCursor = () => {
    if (mode === 'agent-processing' || mode === 'verifying') return 'wait';
    if (mode === 'calibrate' || mode === 'draw') return 'crosshair';
    return 'default';
  };

  return (
    <div
      className="w-full h-full overflow-auto flex items-start justify-start p-8 bg-slate-200/50"
      ref={containerRef}
    >
      <div className="relative inline-block shadow-2xl rounded-sm overflow-hidden ring-1 ring-slate-200 bg-white">
        <canvas
          ref={canvasRef}
          width={canvasSize.width}
          height={canvasSize.height}
          className="block max-w-none"
          style={{ cursor: getCursor(), maxWidth: '100%', height: 'auto' }}
          onMouseMove={handleMouseMove}
          onMouseDown={handleMouseDown}
          onDoubleClick={handleDoubleClick}
        />
      </div>
    </div>
  );
};

export default Canvas;
