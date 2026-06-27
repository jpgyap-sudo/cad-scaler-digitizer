"""Engineering validators — dimension, structural, joinery, hardware clearance, manufacturing.
Each validates a ReadyForCADPackage and returns ValidationIssue list.
"""
from typing import List
from .models import ValidationIssue


class BaseValidator:
    def validate(self, package) -> List[ValidationIssue]:
        raise NotImplementedError

    def issue(self, severity: str, code: str, message: str, fix: str = None, field: str = None):
        return ValidationIssue(severity=severity, code=code, message=message, suggested_fix=fix, field=field)

    def err(self, *a, **kw): return self.issue("error", *a, **kw)
    def warn(self, *a, **kw): return self.issue("warning", *a, **kw)
    def info(self, *a, **kw): return self.issue("info", *a, **kw)


class DimensionValidator(BaseValidator):
    def validate(self, package) -> List[ValidationIssue]:
        issues = []; p = package.cad_parameters
        pt = package.product_type
        h = p.get("height_mm", 0)
        d = p.get("depth_mm", 0)
        L = p.get("length_mm", 0)

        # Dining table height must be 720-780mm
        if pt in ("dining_table","asymmetric_pedestal_table","oval_pedestal_table",
                  "rectangular_table","console_table","round_pedestal_table"):
            if h and not (720 <= h <= 780):
                issues.append(self.warn("DIM-001", f"Dining table height {h}mm outside 720-780mm range.",
                                        f"Adjust to 750mm.", "height_mm"))
            if L and d and L < d:
                issues.append(self.warn("DIM-002", f"Length {L}mm < depth {d}mm. Possible orientation issue.", field="length_mm"))

        # Coffee table height
        if pt == "coffee_table" and h and not (300 <= h <= 480):
            issues.append(self.warn("DIM-003", f"Coffee table height {h}mm outside 300-480mm range.", "Adjust to 380mm.", "height_mm"))

        # Sofa seat height
        if pt in ("sofa","lounge_chair"):
            sh = p.get("seat_height_mm", 0)
            if sh and not (380 <= sh <= 460):
                issues.append(self.warn("DIM-004", f"Seat height {sh}mm outside 380-460mm.", "Adjust to 420mm.", "seat_height_mm"))

        # Desk depth
        if pt in ("office_desk","desk") and d and d < 500:
            issues.append(self.err("DIM-005", f"Desk depth {d}mm < 500mm minimum. Increase depth.", field="depth_mm"))

        return issues


class StructuralValidator(BaseValidator):
    def validate(self, package) -> List[ValidationIssue]:
        issues = []; p = package.cad_parameters; pt = package.product_type

        # Long stone top needs hidden support
        if pt in ("dining_table","asymmetric_pedestal_table","oval_pedestal_table","rectangular_table","console_table"):
            L = p.get("length_mm", 0)
            T = p.get("top_thickness_mm", p.get("thickness_mm", 0))
            if L > 1800 and T and T < 30:
                issues.append(self.warn("STR-001", f"Stone top {L}mm long but only {T}mm thick.",
                                        "Increase top thickness to 30mm or specify hidden steel frame.", "top_thickness_mm"))
            if L > 2400:
                issues.append(self.warn("STR-002", f"Oversize top {L}mm. Verify structural support and lifting plan."))

        # Pedestal stability: base footprint
        large = p.get("large_pedestal_diameter_mm", p.get("pedestal_diameter_mm", 0))
        if large and d:
            if large < 200:
                issues.append(self.warn("STR-003", f"Pedestal Ø{large}mm may be unstable for given top size.", "Increase pedestal diameter."))
        return issues


class JoineryValidator(BaseValidator):
    def validate(self, package) -> List[ValidationIssue]:
        issues = []
        pt = package.product_type
        p = package.cad_parameters
        L = p.get("length_mm", 0)
        if pt in ("sideboard","tv_console","cabinet","wardrobe") and L > 1800:
            issues.append(self.warn("JNY-001", f"Cabinet span {L}mm > 1800mm. Add center divider or thicker shelves."))
        return issues


class HardwareClearanceValidator(BaseValidator):
    def validate(self, package) -> List[ValidationIssue]:
        issues = []
        p = package.cad_parameters
        if p.get("door_count", 0) > 0 and p.get("length_mm", 0) > 0:
            door_w = p["length_mm"] / max(p.get("door_count", 2), 1)
            if door_w > 600:
                issues.append(self.warn("HWC-001", f"Door width {door_w:.0f}mm > 600mm. Use heavier hinges or reduce door width."))
        return issues


class ManufacturingValidator(BaseValidator):
    def validate(self, package) -> List[ValidationIssue]:
        issues = []
        mp = package.manufacturing_plan
        if mp and not mp.production_steps:
            issues.append(self.err("MFG-001", "No production steps defined. Manufacturing plan is empty."))
        if mp and not mp.cutting_list and package.product_type not in ("",):
            issues.append(self.warn("MFG-002", "No cutting list. Verify material quantities."))
        return issues
