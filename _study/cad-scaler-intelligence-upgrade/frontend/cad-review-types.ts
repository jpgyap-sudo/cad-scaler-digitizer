export type CadEntitySource =
  | "pixel_detected"
  | "ocr_associated"
  | "user_confirmed"
  | "reference_estimated"
  | "template_default";

export interface CadEntity {
  id: string;
  type: "line" | "circle" | "polyline" | "text";
  geometry: Record<string, any>;
  source: CadEntitySource;
  confidence: number;
  evidence: string[];
  layer: string;
  metadata: Record<string, any>;
}

export interface ManualCorrection {
  action: "set_line_role" | "confirm_scale" | "set_entity_confidence";
  line_id?: string;
  role?: string;
  entity_id?: string;
  confidence?: number;
  mm_per_px?: number;
}
