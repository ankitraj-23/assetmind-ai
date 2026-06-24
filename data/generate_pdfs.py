from fpdf import FPDF
import os

OUT = os.path.join(os.path.dirname(__file__), "documents")
os.makedirs(OUT, exist_ok=True)

L_MARGIN = 15
R_MARGIN = 15
T_MARGIN = 15


def new_pdf():
    pdf = FPDF()
    pdf.set_margins(L_MARGIN, T_MARGIN, R_MARGIN)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    return pdf


def ew(pdf):
    return pdf.w - pdf.l_margin - pdf.r_margin


def heading(pdf, text):
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(ew(pdf), 9, text)


def sub(pdf, text):
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(ew(pdf), 6, text)
    pdf.ln(2)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(4)


def section(pdf, title, body):
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(ew(pdf), 7, title)
    pdf.set_font("Helvetica", size=10)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(ew(pdf), 6, body)
    pdf.ln(3)


# ─────────────────────────────────────────────
# 1. OEM PUMP MANUAL
# ─────────────────────────────────────────────
def make_oem_manual():
    pdf = new_pdf()
    heading(pdf, "Centrifugal Pump Operations & Maintenance Manual")
    sub(pdf, "Applies to: P-101, P-102, P-201  |  Doc ID: OEM-PUMP-CM-001  |  Rev: 5  |  Date: 2024-01-10")

    section(pdf, "1. Equipment Overview",
        "P-101, P-102, and P-201 are horizontal end-suction centrifugal pumps rated at "
        "45 m3/h at 32 m head. Operating speed: 1450 RPM driven by 11 kW induction motors. "
        "Mechanical seal type: single cartridge spring-loaded, API Plan 11 flush. "
        "Bearing arrangement: drive end 6309-2RS, non-drive end 6206-2RS."
    )

    section(pdf, "2. Startup Procedure",
        "Refer to SOP-PUMP-07 for the full startup sequence. Key pre-start checks: "
        "verify suction valve fully open, confirm seal flush pressure above 0.8 bar, "
        "check oil level at bearing housing sight glass, and ensure coupling guard is fitted."
    )

    section(pdf, "3. Maintenance Schedule",
        "Weekly: check bearing temperature (max 75 deg C), inspect seal flush flow "
        "(min 2 L/min), check for leakage at gland.\n"
        "Monthly: verify coupling alignment (max 0.05 mm TIR), measure vibration.\n"
        "6-Monthly: replace bearing grease (Mobilux EP2, 15 g per bearing).\n"
        "Annual: replace mechanical seal cartridge MS-45-CR, inspect impeller for "
        "cavitation damage, replace wear ring if clearance exceeds 0.5 mm."
    )

    section(pdf, "4. Vibration Standards (OISD-137)",
        "Per OISD-137, maximum allowable vibration velocity is 4.5 mm/s RMS. "
        "Alarm setpoint: 3.5 mm/s. Trip setpoint: 7.0 mm/s. Any reading above "
        "4.5 mm/s requires investigation within 48 hours. Measurements must be taken "
        "at the bearing housing in vertical, horizontal, and axial directions."
    )

    section(pdf, "5. Common Failure Modes",
        "1. Mechanical seal leakage: caused by misalignment greater than 0.1 mm TIR, "
        "incorrect flush pressure, or seal face damage from dry running. Corrective action: "
        "replace cartridge seal MS-45-CR and verify alignment per SOP-PUMP-07.\n\n"
        "2. Bearing overheating above 75 deg C: caused by over-greasing, under-greasing, "
        "or contaminated lubricant. Replace bearing 6309-2RS if temperature exceeds 85 deg C.\n\n"
        "3. High vibration above 4.5 mm/s: caused by misalignment, cavitation, worn impeller, "
        "or unbalanced rotor. Check shaft alignment first, then verify NPSH available.\n\n"
        "4. Cavitation: occurs when suction pressure drops below NPSHr of 3.2 m. "
        "Check suction strainer differential pressure and verify vessel level.\n\n"
        "5. Motor overload trip: caused by high-density product, partially closed discharge "
        "valve, or impeller damage. Verify motor FLC on nameplate and check VFD parameters."
    )

    section(pdf, "6. Spare Parts List",
        "Mechanical seal cartridge: MS-45-CR (annual consumable)\n"
        "Drive end bearing: 6309-2RS\n"
        "Non-drive end bearing: 6206-2RS\n"
        "Wear ring set: WR-P101-CR\n"
        "Coupling insert: CI-HRC-70\n"
        "Gland packing backup: GP-12.7-AF"
    )

    path = os.path.join(OUT, "pump_oem_manual.pdf")
    pdf.output(path)
    print(f"Created: {path}")


# ─────────────────────────────────────────────
# 2. SOP - PUMP STARTUP
# ─────────────────────────────────────────────
def make_sop_pump_startup():
    pdf = new_pdf()
    heading(pdf, "Standard Operating Procedure: Centrifugal Pump Startup and Shutdown")
    sub(pdf, "SOP ID: SOP-PUMP-07  |  Rev: 3  |  Approved: 2024-03-01  |  Applies to: P-101, P-102, P-201")

    section(pdf, "1. Pre-Startup Checks",
        "1.1 Confirm maintenance work order is closed and equipment returned to service.\n"
        "1.2 Verify all isolation valves on suction line are fully open.\n"
        "1.3 Check mechanical seal flush line is open; flush pressure must read 0.8 to 1.2 bar.\n"
        "1.4 Confirm bearing housing oil level is between MIN and MAX marks on sight glass.\n"
        "1.5 Check coupling guard is fitted and all bolts are torqued.\n"
        "1.6 Set discharge valve to 25 percent open. Never start against a fully closed "
        "or fully open discharge valve.\n"
        "1.7 Manually rotate pump shaft to confirm free rotation. Resistance indicates "
        "seized bearing or locked seal - do not attempt to start."
    )

    section(pdf, "2. Startup Sequence",
        "2.1 Energise motor from MCC panel. Confirm green running indication.\n"
        "2.2 Slowly open discharge valve to duty point over 30 seconds.\n"
        "2.3 Confirm discharge pressure stabilises at design value within plus or minus 10 percent.\n"
        "2.4 Measure vibration at bearing housing within 5 minutes. Must be below 4.5 mm/s "
        "per OISD-137. Shut down immediately if reading exceeds 4.5 mm/s.\n"
        "2.5 Check bearing temperature within 15 minutes. Must be below 70 deg C.\n"
        "2.6 Inspect gland area for leakage. Maximum acceptable: 10 drops per minute.\n"
        "2.7 Record startup in maintenance register with date, time, and technician signature."
    )

    section(pdf, "3. Normal Shutdown",
        "3.1 Partially close discharge valve to 25 percent open.\n"
        "3.2 De-energise motor from MCC panel.\n"
        "3.3 Close discharge valve fully once pump comes to a complete stop.\n"
        "3.4 Close suction valve if pump is to be isolated for maintenance.\n"
        "3.5 Depressurise and drain casing before any mechanical work begins."
    )

    section(pdf, "4. Emergency Shutdown",
        "4.1 De-energise motor immediately from nearest isolation point.\n"
        "4.2 Do not attempt to restart until root cause of emergency is identified.\n"
        "4.3 Raise maintenance work order in CMMS system within 30 minutes.\n"
        "4.4 Notify shift supervisor immediately."
    )

    section(pdf, "5. Safety Precautions",
        "5.1 Follow LOTO procedure HSE-LOTO-001 before any mechanical work.\n"
        "5.2 Mandatory PPE: safety glasses, chemical-resistant gloves, steel-toed boots.\n"
        "5.3 Never open pump casing while pressurised. Depressurise to zero before opening.\n"
        "5.4 Refer to MSDS for the product being pumped before any maintenance task."
    )

    path = os.path.join(OUT, "sop_pump_startup.pdf")
    pdf.output(path)
    print(f"Created: {path}")


# ─────────────────────────────────────────────
# 3. INSPECTION REPORT Q1 2025
# ─────────────────────────────────────────────
def make_inspection_report():
    pdf = new_pdf()
    heading(pdf, "Quarterly Plant Inspection Report - Q1 2025")
    sub(pdf, "Inspection Date: 15 March 2025  |  Inspector: R. Kumar (Senior Mechanical Engineer)  |  Building B02, North Region")

    section(pdf, "P-101 - Cooling Water Pump  [Risk: HIGH]",
        "Vibration at drive end bearing: 6.2 mm/s RMS. Exceeds OISD-137 limit of 4.5 mm/s. "
        "Visual inspection reveals slight misalignment of flexible coupling. Last seal replacement "
        "on 12 January 2025 per work order WO-20000019. Bearing temperature 71 deg C, within limit. "
        "Recommendation: perform laser alignment check within 48 hours. If vibration remains above "
        "4.5 mm/s after alignment, replace drive end bearing 6309-2RS."
    )

    section(pdf, "P-102 - Feed Transfer Pump  [Risk: LOW]",
        "Bearing temperature: 68 deg C. Vibration: 3.1 mm/s, within OISD-137 limit. "
        "Seal flush flow confirmed at 2.4 L/min, above minimum 2.0 L/min. No leakage at gland. "
        "No issues found. Next inspection: June 2025."
    )

    section(pdf, "P-201 - Condensate Extraction Pump  [Risk: LOW]",
        "Vibration: 2.8 mm/s, well within OISD-137 limit. Bearing temperature 65 deg C. "
        "Seal flush pressure 0.95 bar, within 0.8 to 1.2 bar range. No issues found. "
        "Next inspection: June 2025."
    )

    section(pdf, "TK-482 - Feed Storage Tank  [Risk: MEDIUM]",
        "Level transmitter LT-482-01 calibration is overdue by 45 days. Last calibration: "
        "October 2024. Per Factory Act Schedule VIII, level instruments on process tanks must "
        "be calibrated every 6 months. Tank shell shows no visible corrosion. Nitrogen blanket "
        "pressure at 0.05 bar. Action required: complete calibration before 30 March 2025."
    )

    section(pdf, "HX-305 - Shell and Tube Heat Exchanger  [Risk: MEDIUM]",
        "Shell side outlet temperature is 12 deg C below design, indicating tube fouling. "
        "Pressure drop across tube side increased from 0.8 bar to 1.4 bar since December 2024. "
        "Estimated heat transfer efficiency loss: 18 percent. Tube bundle chemical cleaning "
        "recommended during next planned shutdown. No tube leakage detected."
    )

    section(pdf, "BLR-118 - Package Boiler  [Risk: CRITICAL]",
        "Pressure test certificate expired on 01 February 2025. Under PESO regulations and "
        "Factories Act Section 31, a valid pressure test certificate is mandatory for boiler "
        "operation. Operating without a valid certificate constitutes a regulatory violation "
        "and exposes the facility to shutdown notice. Immediate action required: contact "
        "approved inspection authority. Do not defer beyond 31 March 2025."
    )

    section(pdf, "R-201 - Process Reactor  [Risk: MEDIUM]",
        "Safety relief valve SRV-R201-01 last tested: September 2023. Per OISD-116, safety "
        "relief valves on process reactors must be bench-tested every 18 months. Test is due "
        "March 2025. Schedule bench test at approved facility before 30 April 2025."
    )

    section(pdf, "M-017 - Boiler Feed Motor  [Risk: LOW]",
        "Insulation resistance: 85 MOhm (healthy, minimum 1 MOhm per IEC 60034). "
        "Winding temperature within limits. Terminal connections show no heat discolouration. "
        "Vibration at motor bearing: 2.2 mm/s. No issues found."
    )

    section(pdf, "Inspection Summary",
        "Total assets inspected: 8\n"
        "Compliant (no issues): 4 - P-102, P-201, M-017, partial HX-305\n"
        "Action required: 3 - P-101 vibration, TK-482 calibration, R-201 SRV test\n"
        "Critical immediate action: 1 - BLR-118 pressure certificate\n"
        "Next full inspection: June 2025"
    )

    path = os.path.join(OUT, "inspection_report_q1_2025.pdf")
    pdf.output(path)
    print(f"Created: {path}")


# ─────────────────────────────────────────────
# 4. COMPLIANCE CHECKLIST
# ─────────────────────────────────────────────
def make_compliance_checklist():
    pdf = new_pdf()
    heading(pdf, "Plant Compliance and Regulatory Checklist - 2025")
    sub(pdf, "Reference: Factory Act 1948, OISD-137, OISD-116, PESO Regulations, ISO 9001:2015")

    section(pdf, "Section A: Pressure Vessels and Boilers",
        "A1. BLR-118 - Annual pressure test certificate: EXPIRED (01-Feb-2025). "
        "Required by Factories Act Section 31 and PESO. Status: NON-COMPLIANT. "
        "Action: schedule inspection authority visit immediately.\n\n"
        "A2. R-201 - Safety relief valve SRV-R201-01 test certificate: DUE March 2025. "
        "Required by OISD-116 every 18 months. Status: ACTION REQUIRED within 30 days."
    )

    section(pdf, "Section B: Rotating Equipment Vibration Monitoring (OISD-137)",
        "B1. P-101 - Vibration inspection: NON-COMPLIANT. Reading 6.2 mm/s exceeds "
        "OISD-137 limit of 4.5 mm/s. Action required within 48 hours.\n\n"
        "B2. P-102 - Vibration inspection: COMPLIANT. Reading 3.1 mm/s. Next due June 2025.\n\n"
        "B3. P-201 - Vibration inspection: COMPLIANT. Reading 2.8 mm/s. Next due June 2025."
    )

    section(pdf, "Section C: Instrumentation Calibration (Factory Act Schedule VIII)",
        "C1. TK-482 Level Transmitter LT-482-01 - Calibration: OVERDUE by 45 days. "
        "Required every 6 months. Status: NON-COMPLIANT. Must complete by 30 March 2025.\n\n"
        "C2. HX-305 Temperature Instruments - Calibration: CURRENT. Status: COMPLIANT.\n\n"
        "C3. M-017 Motor Protection Relay - Calibration: CURRENT. Status: COMPLIANT."
    )

    section(pdf, "Section D: SOP and Procedure Review",
        "D1. SOP-PUMP-07 (Pump Startup and Shutdown) - Last reviewed: March 2024. "
        "Review cycle: 12 months. Next due: March 2025. Status: DUE FOR REVIEW.\n\n"
        "D2. HSE-LOTO-001 (Lockout-Tagout) - Last reviewed: November 2023. "
        "Status: OVERDUE for review by 6 months.\n\n"
        "D3. SOP-BOILER-01 (Boiler Startup) - Last reviewed: January 2025. "
        "Status: COMPLIANT."
    )

    section(pdf, "Section E: Quality Non-Conformances (ISO 9001:2015)",
        "E1. HX-305 tube fouling - NCR raised 15 March 2025. RCA pending. "
        "Target closure: 30 April 2025.\n\n"
        "E2. P-101 vibration exceedance - NCR raised 15 March 2025. Alignment check "
        "scheduled 17 March 2025. Target closure: 20 March 2025.\n\n"
        "E3. BLR-118 certificate lapse - NCR raised 01 February 2025. "
        "Inspection scheduled 25 March 2025. Target closure: 31 March 2025."
    )

    section(pdf, "Compliance Summary",
        "Total items checked: 16\n"
        "Compliant: 9\n"
        "Non-compliant: 3 - BLR-118 pressure cert, P-101 vibration, TK-482 calibration\n"
        "Action required within 30 days: 2 - R-201 SRV test, SOP-PUMP-07 review\n"
        "Critical (immediate): 1 - BLR-118\n"
        "Audit readiness score: 6.2 out of 10. Target: 9.0 by Q2 2025."
    )

    path = os.path.join(OUT, "compliance_checklist_2025.pdf")
    pdf.output(path)
    print(f"Created: {path}")


if __name__ == "__main__":
    make_oem_manual()
    make_sop_pump_startup()
    make_inspection_report()
    make_compliance_checklist()
    print("\nAll 4 PDFs generated in data/documents/")
