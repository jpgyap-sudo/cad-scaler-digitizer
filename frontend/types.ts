// === Core Geometric ===
export interface Point {
  x: number;
  y: number;
}

// === CAD Primitives ===
export type CadPrimitiveType =
  | 'circle'
  | 'arc'
  | 'rectangle'
  | 'polyline'
  | 'line'
  | 'centerline'
  | 'dimension'
  | 'text';

export interface CadCircle {
  type: 'circle';
  center: Point;
  radius: number;
  layer?: string;
  style?: 'solid' | 'hidden' | 'center';
}

export interface CadArc {
  type: 'arc';
  center: Point;
  radius: number;
  startAngle: number;
  endAngle: number;
  layer?: string;
}

export interface CadRectangle {
  type: 'rectangle';
  p1: Point;
  p2: Point;
  width: number;
  height: number;
  layer?: string;
}

export interface CadPolyline {
  type: 'polyline';
  points: Point[];
  closed: boolean;
  layer?: string;
}

export interface CadLine {
  type: 'line';
  p1: Point;
  p2: Point;
  style?: 'solid' | 'hidden' | 'center' | 'dimension';
  layer?: string;
}

export interface CadCenterline {
  type: 'centerline';
  p1: Point;
  p2: Point;
  layer?: string;
}

export interface CadDimension {
  type: 'dimension';
  p1: Point;
  p2: Point;
  value: number;
  unit: string;
  orientation: 'horizontal' | 'vertical' | 'aligned';
  layer?: string;
}

export interface CadText {
  type: 'text';
  position: Point;
  content: string;
  height?: number;
  layer?: string;
}

export type CadPrimitive =
  | CadCircle | CadArc | CadRectangle | CadPolyline
  | CadLine | CadCenterline | CadDimension | CadText;

// === Drawing View ===
export interface CadView {
  name: string;
  scale: number;
  origin: Point;
  primitives: CadPrimitive[];
}

// === Full CAD Document from Gemini ===
export interface CadDocument {
  title: string;
  views: CadView[];
  calibration?: {
    found: boolean;
    pixelsPerUnit: number;
    originalScale?: string;
  };
  templateMatch?: ParametricMatch;
}

// === Parametric Templates ===
export interface ParametricTemplateParameter {
  name: string;
  default: number;
  unit: string;
  description: string;
}

export interface ParametricTemplateView {
  view: 'top' | 'front' | 'side';
  primitives: CadPrimitive[];
}

export interface ParametricTemplate {
  name: string;
  type: string;
  parameters: ParametricTemplateParameter[];
  views: ParametricTemplateView[];
}

export interface ParametricMatch {
  templateName: string;
  type: string;
  parameters: Record<string, number>;
  confidence: number;
}

// === App State Types (kept from original) ===
export type AppMode = 'idle' | 'calibrate' | 'draw' | 'agent-processing' | 'verifying';

export interface VerificationResult {
  score: number;
  feedback: string[];
  approved: boolean;
}

// === Legacy types kept for backward compat during migration ===
export interface Polyline {
  id: string;
  points: Point[];
}

export interface Calibration {
  p1: Point;
  p2: Point;
  realLength: number;
  unit: string;
}
