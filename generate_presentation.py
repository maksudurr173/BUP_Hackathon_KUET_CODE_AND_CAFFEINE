"""Presentation Generator for GridWise.

Generates both PPTX (Widescreen 16:9) and PDF slide decks in the docs/ folder
with high-aesthetic formatting, clear architecture diagrams, metrics, and key highlights.
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Brand Palette Constants
GRAPHITE = RGBColor(0x17, 0x21, 0x26)
TEAL = RGBColor(0x14, 0x9E, 0x9A)
AMBER = RGBColor(0xE5, 0xA9, 0x3D)
MINT = RGBColor(0xDC, 0xEF, 0xE8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARK_CARD = RGBColor(0x22, 0x2E, 0x35)
LIGHT_BG = RGBColor(0xF6, 0xF8, 0xF7)
TEXT_MUTED = RGBColor(0x93, 0xA1, 0xA6)
TEXT_LIGHT = RGBColor(0xEE, 0xF4, 0xF3)
ACCENT_GREEN = RGBColor(0x2E, 0xCC, 0x71)

RL_GRAPHITE = colors.HexColor("#172126")
RL_TEAL = colors.HexColor("#149E9A")
RL_AMBER = colors.HexColor("#E5A93D")
RL_MINT = colors.HexColor("#DCEFE8")
RL_CARD = colors.HexColor("#1E2A30")
RL_MUTED = colors.HexColor("#8A9BA1")
RL_WHITE = colors.HexColor("#FFFFFF")
RL_LIGHT_TEXT = colors.HexColor("#E6EEEC")


# ==============================================================================
# 1. PPTX Generator
# ==============================================================================

def create_pptx(output_path: str):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    def add_header(slide, title_text, category_text="GRIDWISE — BUP HACKATHON 2026"):
        # Header category
        cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.4))
        tf_cat = cat_box.text_frame
        tf_cat.word_wrap = True
        p_cat = tf_cat.paragraphs[0]
        p_cat.text = category_text.upper()
        p_cat.font.size = Pt(11)
        p_cat.font.bold = True
        p_cat.font.color.rgb = TEAL

        # Title
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.75), Inches(11.7), Inches(0.8))
        tf_title = title_box.text_frame
        tf_title.word_wrap = True
        p_title = tf_title.paragraphs[0]
        p_title.text = title_text
        p_title.font.size = Pt(24)
        p_title.font.bold = True
        p_title.font.color.rgb = TEXT_LIGHT

    def set_slide_background(slide, color=GRAPHITE):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        bg.fill.solid()
        bg.fill.fore_color.rgb = color
        bg.line.fill.background()
        return bg

    def add_card(slide, left, top, width, height, bg_color=DARK_CARD, border_color=None):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = bg_color
        if border_color:
            card.line.color.rgb = border_color
            card.line.width = Pt(1.5)
        else:
            card.line.fill.background()
        return card

    # --------------------------------------------------------------------------
    # Slide 1: Title Slide
    # --------------------------------------------------------------------------
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_background(s1, GRAPHITE)

    # Accent decorative glow bar
    glow = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.8), Inches(1.5), Inches(0.08))
    glow.fill.solid()
    glow.fill.fore_color.rgb = AMBER
    glow.line.fill.background()

    # Title box
    tbox = s1.shapes.add_textbox(Inches(0.8), Inches(2.1), Inches(11.5), Inches(3.2))
    tf = tbox.text_frame
    tf.word_wrap = True

    p0 = tf.paragraphs[0]
    p0.text = "GridWise"
    p0.font.size = Pt(54)
    p0.font.bold = True
    p0.font.color.rgb = WHITE

    p1 = tf.add_paragraph()
    p1.text = "LLM-Assisted Smart Campus Energy Optimization Engine"
    p1.font.size = Pt(26)
    p1.font.bold = True
    p1.font.color.rgb = TEAL

    p2 = tf.add_paragraph()
    p2.text = "Bridging Natural Language Operator Directives with Deterministic Mathematical LP Optimization & Enterprise Cyber Defense"
    p2.font.size = Pt(15)
    p2.font.color.rgb = TEXT_MUTED

    # Bottom Meta Card
    add_card(s1, Inches(0.8), Inches(5.6), Inches(11.7), Inches(1.2), DARK_CARD, TEAL)
    meta_box = s1.shapes.add_textbox(Inches(1.1), Inches(5.75), Inches(11.1), Inches(0.9))
    mtf = meta_box.text_frame
    mtf.word_wrap = True
    mp1 = mtf.paragraphs[0]
    mp1.text = "Team: KUET_CODE_AND_CAFFEINE   |   Event: BUP Inter-University Hackathon 2026"
    mp1.font.size = Pt(16)
    mp1.font.bold = True
    mp1.font.color.rgb = WHITE

    mp2 = mtf.add_paragraph()
    mp2.text = "Stack: FastAPI · HiGHS LP Solver (SciPy) · Pydantic v2 · Token-Bucket Defense · Reactive Web Console"
    mp2.font.size = Pt(12)
    mp2.font.color.rgb = TEXT_MUTED

    # --------------------------------------------------------------------------
    # Slide 2: Problem & Motivation
    # --------------------------------------------------------------------------
    s2 = prs.slides.add_slide(blank_layout)
    set_slide_background(s2, GRAPHITE)
    add_header(s2, "The Challenge: Campus Energy Dispatch vs. Operator Intent")

    cards_data_s2 = [
        ("The Energy Dilemma", "Campuses face dynamic TOU peak tariffs (up to 34 BDT/kWh) and intermittent solar generation. Battery storage is crucial but degradation and capacity limits require precise scheduling.", AMBER),
        ("The Operator Gap", "Operators communicate in ambiguous natural language ('clean panels at noon', 'hold 80 kWh reserve'). Converting these to strict physical constraints manually causes delays and errors.", TEAL),
        ("LLM Pitfalls in Energy", "Raw LLMs hallucinate numbers, violate basic physical energy balance (supply != demand), and are vulnerable to prompt injection attacks if allowed to directly output schedules.", ACCENT_GREEN)
    ]

    for i, (title, desc, color) in enumerate(cards_data_s2):
        left = Inches(0.8 + i * 4.0)
        add_card(s2, left, Inches(1.8), Inches(3.7), Inches(4.8), DARK_CARD, color)
        tbox = s2.shapes.add_textbox(left + Inches(0.25), Inches(2.1), Inches(3.2), Inches(4.2))
        tf = tbox.text_frame
        tf.word_wrap = True
        pt = tf.paragraphs[0]
        pt.text = title
        pt.font.size = Pt(18)
        pt.font.bold = True
        pt.font.color.rgb = color

        pd = tf.add_paragraph()
        pd.text = desc
        pd.font.size = Pt(13)
        pd.font.color.rgb = TEXT_LIGHT

    # --------------------------------------------------------------------------
    # Slide 3: GridWise Solution & Core Value
    # --------------------------------------------------------------------------
    s3 = prs.slides.add_slide(blank_layout)
    set_slide_background(s3, GRAPHITE)
    add_header(s3, "GridWise Solution: Deterministic Trust Architecture")

    pillars = [
        ("1. Zero-Hallucination Pipeline", "LLM is strictly confined to interpreting notes into 6 rigid schemas. It NEVER generates raw numerical schedules.", TEAL),
        ("2. Start-Inclusive / End-Exclusive", "Exact physical hour window normalization (e.g., '1 PM to 3 PM' → [13, 14]), ensuring seamless 24h mathematical modeling.", AMBER),
        ("3. Deterministic HiGHS Optimization", "SciPy HiGHS Linear Programming (LP) solver computes mathematically proven global minimum electricity cost in <50ms.", TEAL),
        ("4. Independent Physics Replay", "Every schedule is replayed independently through physics verification (0.01 kWh tolerance) before returning to the user.", ACCENT_GREEN),
        ("5. End-of-Day Neutrality", "Enforces E[23] == E_initial mandatory constraint, preventing artificial battery draining and ensuring sustainable daily cycling.", AMBER),
        ("6. Multi-Layer Cyber Security", "Sliding-window token rate limiting, threat quarantine, prompt-injection defense, and circuit breaker protection.", TEAL),
    ]

    for i, (title, desc, color) in enumerate(pillars):
        row = i // 3
        col = i % 3
        left = Inches(0.8 + col * 4.0)
        top = Inches(1.8 + row * 2.6)
        add_card(s3, left, top, Inches(3.7), Inches(2.3), DARK_CARD, color)
        tbox = s3.shapes.add_textbox(left + Inches(0.2), top + Inches(0.2), Inches(3.3), Inches(1.9))
        tf = tbox.text_frame
        tf.word_wrap = True
        pt = tf.paragraphs[0]
        pt.text = title
        pt.font.size = Pt(15)
        pt.font.bold = True
        pt.font.color.rgb = color

        pd = tf.add_paragraph()
        pd.text = desc
        pd.font.size = Pt(11.5)
        pd.font.color.rgb = TEXT_LIGHT

    # --------------------------------------------------------------------------
    # Slide 4: System Architecture
    # --------------------------------------------------------------------------
    s4 = prs.slides.add_slide(blank_layout)
    set_slide_background(s4, GRAPHITE)
    add_header(s4, "End-to-End System Architecture")

    steps = [
        ("1. Web Frontend", "Interactive Console (SVG Energy Flow & Time Scrubber)", TEAL),
        ("2. Security Middleware", "Rate Limiter · Size Limit (1MB) · IP Quarantine · Security Headers", AMBER),
        ("3. Request Validation", "Strict Pydantic v2 Models (24 Demand/Solar/Tariff arrays + Battery)", TEAL),
        ("4. LLM Interpreter", "Adversarial Pattern Scanner · Start/End Hours · 6 Directive Schemas", ACCENT_GREEN),
        ("5. HiGHS LP Solver", "Min Σ(Grid[h] * Tariff[h]) · Hourly Energy Balance · Neutrality E[23]=E0", TEAL),
        ("6. Physics Replay Validator", "Independent Replay & Recomputed Financial / Physical Totals", AMBER),
    ]

    for i, (title, desc, color) in enumerate(steps):
        left = Inches(0.8 + (i % 2) * 5.9)
        top = Inches(1.8 + (i // 2) * 1.7)
        add_card(s4, left, top, Inches(5.6), Inches(1.5), DARK_CARD, color)
        tbox = s4.shapes.add_textbox(left + Inches(0.25), top + Inches(0.15), Inches(5.1), Inches(1.2))
        tf = tbox.text_frame
        tf.word_wrap = True
        pt = tf.paragraphs[0]
        pt.text = title
        pt.font.size = Pt(15)
        pt.font.bold = True
        pt.font.color.rgb = color

        pd = tf.add_paragraph()
        pd.text = desc
        pd.font.size = Pt(11.5)
        pd.font.color.rgb = TEXT_LIGHT

    # --------------------------------------------------------------------------
    # Slide 5: The 6 Supported Directives
    # --------------------------------------------------------------------------
    s5 = prs.slides.add_slide(blank_layout)
    set_slide_background(s5, GRAPHITE)
    add_header(s5, "Strict Operator Directives & Semantic Normalization")

    directives_data = [
        ("1. solar_reduction", "Modifies usable solar multiplier factor (0.0 to 1.0).\nExample: '80% solar reduction' → factor: 0.2", AMBER),
        ("2. minimum_battery_reserve", "Enforces stored battery energy floor E[h] >= min_energy.\nExample: 'Hold 80 kWh reserve' → min_energy: 80.0", TEAL),
        ("3. no_charge_window", "Prohibits battery from charging during specific hours C[h] = 0.\nExample: 'No charging from 2-4 PM' → hours: [14, 15]", ACCENT_GREEN),
        ("4. no_discharge_window", "Prohibits battery from discharging during hours D[h] = 0.\nExample: 'Avoid discharge from 6-8 PM' → hours: [18, 19]", TEAL),
        ("5. max_grid_window", "Caps electricity grid import G[h] <= max_grid_kwh.\nExample: 'Limit grid intake to 155 kWh' → max_grid: 155.0", AMBER),
        ("6. no_op", "Irrelevant, informational, or distractor notes produce no constraint adjustments (applies = false).", TEXT_MUTED),
    ]

    for i, (title, desc, color) in enumerate(directives_data):
        row = i // 3
        col = i % 3
        left = Inches(0.8 + col * 4.0)
        top = Inches(1.8 + row * 2.6)
        add_card(s5, left, top, Inches(3.7), Inches(2.3), DARK_CARD, color)
        tbox = s5.shapes.add_textbox(left + Inches(0.2), top + Inches(0.2), Inches(3.3), Inches(1.9))
        tf = tbox.text_frame
        tf.word_wrap = True
        pt = tf.paragraphs[0]
        pt.text = title
        pt.font.size = Pt(14)
        pt.font.bold = True
        pt.font.color.rgb = color

        pd = tf.add_paragraph()
        pd.text = desc
        pd.font.size = Pt(11)
        pd.font.color.rgb = TEXT_LIGHT

    # --------------------------------------------------------------------------
    # Slide 6: Mathematical Optimization Model
    # --------------------------------------------------------------------------
    s6 = prs.slides.add_slide(blank_layout)
    set_slide_background(s6, GRAPHITE)
    add_header(s6, "Mathematical Formulation (HiGHS LP Solver)")

    add_card(s6, Inches(0.8), Inches(1.8), Inches(5.6), Inches(4.8), DARK_CARD, TEAL)
    tbox1 = s6.shapes.add_textbox(Inches(1.05), Inches(2.0), Inches(5.1), Inches(4.3))
    tf1 = tbox1.text_frame
    tf1.word_wrap = True
    p = tf1.paragraphs[0]
    p.text = "Objective & Core Dynamics"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = TEAL

    items1 = [
        "Primary Objective: Minimize Total Energy Cost\n  min Σ (Grid[h] × Tariff[h])  for h = 0..23",
        "Fundamental Hourly Energy Balance:\n  Grid[h] + Solar[h] + Discharge[h] = Demand[h] + Charge[h]",
        "Battery State of Charge Transition:\n  E[h] = E[h-1] + Charge[h] - Discharge[h]",
        "Mandatory End-of-Day Neutrality:\n  E[23] == E_initial (Zero daily degradation/bias)"
    ]
    for it in items1:
        pd = tf1.add_paragraph()
        pd.text = it
        pd.font.size = Pt(12)
        pd.font.color.rgb = TEXT_LIGHT

    add_card(s6, Inches(6.9), Inches(1.8), Inches(5.6), Inches(4.8), DARK_CARD, AMBER)
    tbox2 = s6.shapes.add_textbox(Inches(7.15), Inches(2.0), Inches(5.1), Inches(4.3))
    tf2 = tbox2.text_frame
    tf2.word_wrap = True
    p = tf2.paragraphs[0]
    p.text = "Physical Constraints & Bounds"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = AMBER

    items2 = [
        "Solar Curtailment Limit:\n  0 <= SolarUsed[h] <= EffectiveSolar[h]",
        "Battery Operating Bounds:\n  min_reserve[h] <= E[h] <= capacity_kwh",
        "Charge / Discharge Power Limits:\n  0 <= Charge[h] <= max_charge_rate\n  0 <= Discharge[h] <= max_discharge_rate",
        "Deterministic Execution:\n  Solved using HiGHS Interior-Point / Simplex in <50ms with 10s timeout protection."
    ]
    for it in items2:
        pd = tf2.add_paragraph()
        pd.text = it
        pd.font.size = Pt(12)
        pd.font.color.rgb = TEXT_LIGHT

    # --------------------------------------------------------------------------
    # Slide 7: Web Security & Cyber Defense
    # --------------------------------------------------------------------------
    s7 = prs.slides.add_slide(blank_layout)
    set_slide_background(s7, GRAPHITE)
    add_header(s7, "Multi-Layer Web Security & Cyber-Breach Defense")

    sec_cards = [
        ("Prompt Injection Defense", "Regex scanners inspect operator notes for adversarial patterns ('ignore previous instructions', 'eval()', 'reveal keys') and block suspicious input before LLM execution.", TEAL),
        ("LLM Circuit Breaker", "Thread-safe circuit breaker tracks consecutive failures (CLOSED → OPEN → HALF_OPEN), isolating faulty external LLM APIs and preventing cascade failures.", AMBER),
        ("Token-Bucket Rate Limiter", "Per-client sliding window rate limiter (60 req/min + burst capacity) prevents denial-of-service and quota exhaustion.", ACCENT_GREEN),
        ("Client Quarantine Defense", "Threat detector automatically quarantines abusive client IPs for 5 minutes when violation thresholds are breached.", TEAL),
        ("Sanitized Audit Logging", "SOC2-compliant structured JSON logging automatically redacts API keys, passwords, and tokens from all audit trails.", AMBER),
        ("Enterprise HTTP Headers", "Injects CSP, HSTS, X-Frame-Options: DENY, X-Content-Type-Options: nosniff, and granular CORS origin control.", ACCENT_GREEN)
    ]

    for i, (title, desc, color) in enumerate(sec_cards):
        row = i // 3
        col = i % 3
        left = Inches(0.8 + col * 4.0)
        top = Inches(1.8 + row * 2.6)
        add_card(s7, left, top, Inches(3.7), Inches(2.3), DARK_CARD, color)
        tbox = s7.shapes.add_textbox(left + Inches(0.2), top + Inches(0.2), Inches(3.3), Inches(1.9))
        tf = tbox.text_frame
        tf.word_wrap = True
        pt = tf.paragraphs[0]
        pt.text = title
        pt.font.size = Pt(14)
        pt.font.bold = True
        pt.font.color.rgb = color

        pd = tf.add_paragraph()
        pd.text = desc
        pd.font.size = Pt(11)
        pd.font.color.rgb = TEXT_LIGHT

    # --------------------------------------------------------------------------
    # Slide 8: Interactive Frontend Experience
    # --------------------------------------------------------------------------
    s8 = prs.slides.add_slide(blank_layout)
    set_slide_background(s8, GRAPHITE)
    add_header(s8, "GridWise Web Console: Modern Operator Experience")

    ui_features = [
        ("Dynamic 24h SVG Energy Flow", "Real-time animated energy routing between Solar, Grid, Demand, and Battery with a 24-hour playback scrubber.", TEAL),
        ("Interactive SVG Charting Suite", "Multi-view data visualizations: Solar vs Available, Grid draw, Battery SoC curves, TOU tariff heatmaps, and hourly cost bars.", AMBER),
        ("Live Directive Interpretation Preview", "Instant badge feedback as operators type instructions, previewing normalized hour windows and affected constraint parameters.", ACCENT_GREEN),
        ("Scenario Benchmarking & JSON Export", "Built-in preset loader with all 10 official BUP Hackathon cases, comparison manager, and one-click JSON export.", TEAL)
    ]

    for i, (title, desc, color) in enumerate(ui_features):
        left = Inches(0.8 + (i % 2) * 5.9)
        top = Inches(1.8 + (i // 2) * 2.5)
        add_card(s8, left, top, Inches(5.6), Inches(2.2), DARK_CARD, color)
        tbox = s8.shapes.add_textbox(left + Inches(0.25), top + Inches(0.2), Inches(5.1), Inches(1.8))
        tf = tbox.text_frame
        tf.word_wrap = True
        pt = tf.paragraphs[0]
        pt.text = title
        pt.font.size = Pt(16)
        pt.font.bold = True
        pt.font.color.rgb = color

        pd = tf.add_paragraph()
        pd.text = desc
        pd.font.size = Pt(12)
        pd.font.color.rgb = TEXT_LIGHT

    # --------------------------------------------------------------------------
    # Slide 9: Verification & Benchmark Results
    # --------------------------------------------------------------------------
    s9 = prs.slides.add_slide(blank_layout)
    set_slide_background(s9, GRAPHITE)
    add_header(s9, "Verification, Testing & Benchmark Results")

    # Left stats column
    stats = [
        ("38 / 38", "Automated Tests Passed (100%)", TEAL),
        ("10 / 10", "Official BUP Benchmark Cases Solved", AMBER),
        ("< 50 ms", "Average LP Optimization Time", ACCENT_GREEN),
        ("0.01 kWh", "Physical Replay Tolerance", TEAL)
    ]

    for i, (val, label, color) in enumerate(stats):
        top = Inches(1.8 + i * 1.25)
        add_card(s9, Inches(0.8), top, Inches(3.8), Inches(1.1), DARK_CARD, color)
        tbox = s9.shapes.add_textbox(Inches(1.0), top + Inches(0.1), Inches(3.4), Inches(0.9))
        tf = tbox.text_frame
        tf.word_wrap = True
        pt = tf.paragraphs[0]
        pt.text = val
        pt.font.size = Pt(22)
        pt.font.bold = True
        pt.font.color.rgb = color

        pd = tf.add_paragraph()
        pd.text = label
        pd.font.size = Pt(11)
        pd.font.color.rgb = TEXT_LIGHT

    # Right test suite breakdown
    add_card(s9, Inches(5.0), Inches(1.8), Inches(7.5), Inches(4.85), DARK_CARD, TEAL)
    tbox_r = s9.shapes.add_textbox(Inches(5.3), Inches(2.0), Inches(6.9), Inches(4.4))
    tfr = tbox_r.text_frame
    tfr.word_wrap = True
    p = tfr.paragraphs[0]
    p.text = "Comprehensive Test Suite Coverage"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = TEAL

    test_items = [
        "test_validation.py — Array lengths (exactly 24), non-negativity, battery bounds.",
        "test_directives.py — All 6 directive types, multiple directive composition, hour normalization.",
        "test_llm_guardrails.py — Prompt injection blocking, circuit breaker state transitions, JSON extraction.",
        "test_optimizer.py — LP optimality, battery neutrality, reserve floors, charge/discharge block windows.",
        "test_schedule_validator.py — Independent replay verification, deliberate corruption detection.",
        "test_security.py — Token bucket rate limiting, IP quarantine, JWT auth, RBAC roles.",
        "test_public_cases.py — End-to-end integration across high solar, multi-directive challenge profiles."
    ]
    for it in test_items:
        pd = tfr.add_paragraph()
        pd.text = f"• {it}"
        pd.font.size = Pt(11.5)
        pd.font.color.rgb = TEXT_LIGHT

    # --------------------------------------------------------------------------
    # Slide 10: Conclusion & Impact
    # --------------------------------------------------------------------------
    s10 = prs.slides.add_slide(blank_layout)
    set_slide_background(s10, GRAPHITE)
    add_header(s10, "Conclusion: Ready for Real-World Microgrids")

    add_card(s10, Inches(0.8), Inches(1.8), Inches(11.7), Inches(4.8), DARK_CARD, TEAL)
    tbox_c = s10.shapes.add_textbox(Inches(1.2), Inches(2.1), Inches(10.9), Inches(4.2))
    tfc = tbox_c.text_frame
    tfc.word_wrap = True

    p = tfc.paragraphs[0]
    p.text = "Why GridWise Stands Out"
    p.font.size = Pt(22)
    p.font.bold = True
    p.font.color.rgb = AMBER

    conclusions = [
        "Deterministic Trust: Separates language reasoning from physical math. No hallucinations, guaranteed minimum-cost.",
        "Complete Web-Native Integration: Direct connection between modern frontend UI and FastAPI HiGHS optimization engine.",
        "Production-Grade Security: Cyber-breach detection, sliding-window rate limiting, token sanitization, and fail-closed safety.",
        "Deployment Ready: Fully containerized with Docker, lightweight footprint, and zero external binary dependencies.",
        "Scalability: Ready to scale from university campuses to industrial parks, hospital microgrids, and EV charging hubs."
    ]
    for c in conclusions:
        pd = tfc.add_paragraph()
        pd.text = f"✔  {c}"
        pd.font.size = Pt(13.5)
        pd.font.color.rgb = TEXT_LIGHT

    prs.save(output_path)
    print(f"PPTX saved to {output_path}")


# ==============================================================================
# 2. PDF Generator (ReportLab Landscape Presentation Deck)
# ==============================================================================

def create_pdf(output_path: str):
    # Landscape Letter size: 11 x 8.5 inches
    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(letter),
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    style_category = ParagraphStyle(
        "Category",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=RL_TEAL,
        spaceAfter=4,
    )

    style_title = ParagraphStyle(
        "SlideTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=RL_WHITE,
        spaceAfter=14,
    )

    style_hero_title = ParagraphStyle(
        "HeroTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=38,
        leading=42,
        textColor=RL_WHITE,
        spaceAfter=8,
    )

    style_hero_sub = ParagraphStyle(
        "HeroSub",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=RL_TEAL,
        spaceAfter=10,
    )

    style_body = ParagraphStyle(
        "SlideBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        textColor=RL_LIGHT_TEXT,
    )

    style_card_title = ParagraphStyle(
        "CardTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=RL_AMBER,
        spaceAfter=6,
    )

    style_card_title_teal = ParagraphStyle(
        "CardTitleTeal",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=RL_TEAL,
        spaceAfter=6,
    )

    style_stat_val = ParagraphStyle(
        "StatVal",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=22,
        textColor=RL_TEAL,
        spaceAfter=3,
    )

    style_stat_lbl = ParagraphStyle(
        "StatLbl",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=12,
        textColor=RL_LIGHT_TEXT,
    )

    def draw_bg(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(RL_GRAPHITE)
        canvas.rect(0, 0, 11 * inch, 8.5 * inch, fill=True, stroke=False)
        # Top Accent Line
        canvas.setFillColor(RL_TEAL)
        canvas.rect(0.5 * inch, 8.1 * inch, 10.0 * inch, 3, fill=True, stroke=False)
        canvas.restoreState()

    story = []

    # Slide 1: Title
    story.append(Spacer(1, 1.2 * inch))
    story.append(Paragraph("GRIDWISE", style_hero_title))
    story.append(Paragraph("LLM-Assisted Smart Campus Energy Optimization Engine", style_hero_sub))
    story.append(Paragraph("Bridging Operator Natural Language with Deterministic LP Optimization & Enterprise Cyber Defense", style_body))
    story.append(Spacer(1, 0.8 * inch))

    meta_content = [
        [Paragraph("<b>Team:</b> KUET_CODE_AND_CAFFEINE", style_body), Paragraph("<b>Event:</b> BUP Hackathon 2026", style_body)],
        [Paragraph("<b>Backend Stack:</b> FastAPI · HiGHS LP Solver (SciPy) · Pydantic v2", style_body), Paragraph("<b>Frontend:</b> Responsive SVG Console", style_body)]
    ]
    meta_table = Table(meta_content, colWidths=[5.0 * inch, 4.8 * inch])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), RL_CARD),
        ('BOX', (0, 0), (-1, -1), 1.5, RL_TEAL),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(meta_table)
    story.append(PageBreak())

    # Slide 2: The Challenge
    story.append(Paragraph("THE CHALLENGE", style_category))
    story.append(Paragraph("Campus Energy Dispatch vs. Operator Intent", style_title))
    
    col1 = [
        Paragraph("The Energy Dilemma", style_card_title),
        Paragraph("Campuses face dynamic TOU peak tariffs (up to 34 BDT/kWh) and intermittent solar generation. Battery storage is crucial but degradation and capacity limits require precise scheduling.", style_body)
    ]
    col2 = [
        Paragraph("The Operator Gap", style_card_title_teal),
        Paragraph("Operators communicate in natural language ('clean panels at noon', 'hold 80 kWh reserve'). Converting these to strict physical constraints manually causes delays and human errors.", style_body)
    ]
    col3 = [
        Paragraph("LLM Pitfalls in Energy", style_card_title),
        Paragraph("Raw LLMs hallucinate numbers, violate basic physical energy balance (supply != demand), and are vulnerable to prompt injection attacks if allowed to directly output schedules.", style_body)
    ]

    t2 = Table([[col1, col2, col3]], colWidths=[3.2 * inch, 3.2 * inch, 3.2 * inch])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), RL_CARD),
        ('BOX', (0, 0), (0, 0), 1.2, RL_AMBER),
        ('BOX', (1, 0), (1, 0), 1.2, RL_TEAL),
        ('BOX', (2, 0), (2, 0), 1.2, RL_AMBER),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t2)
    story.append(PageBreak())

    # Slide 3: Solution Architecture
    story.append(Paragraph("ARCHITECTURE & PIPELINE", style_category))
    story.append(Paragraph("Zero-Hallucination Deterministic Pipeline", style_title))

    arch_data = [
        [Paragraph("1. Web Frontend", style_card_title_teal), Paragraph("Interactive Console (SVG Energy Flow & Time Scrubber)", style_body)],
        [Paragraph("2. Security Middleware", style_card_title), Paragraph("Token-Bucket Rate Limiter · 1MB Payload Cap · IP Quarantine · Security Headers", style_body)],
        [Paragraph("3. Request Validation", style_card_title_teal), Paragraph("Strict Pydantic v2 Models (24 Demand/Solar/Tariff arrays + Battery Physics)", style_body)],
        [Paragraph("4. LLM Interpreter", style_card_title), Paragraph("Adversarial Pattern Scanner · Start-Inclusive/End-Exclusive Normalization · 6 Schemas", style_body)],
        [Paragraph("5. HiGHS LP Solver", style_card_title_teal), Paragraph("Min Σ(Grid[h] * Tariff[h]) · Hourly Energy Balance · Mandatory End-of-Day Neutrality E[23]=E0", style_body)],
        [Paragraph("6. Physics Replay Validator", style_card_title), Paragraph("Independent Replay Engine · Tolerance Check (0.01 kWh) · Recomputed Final Totals", style_body)],
    ]
    t_arch = Table(arch_data, colWidths=[3.0 * inch, 6.8 * inch])
    t_arch.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), RL_CARD),
        ('BOX', (0, 0), (-1, -1), 1.2, RL_TEAL),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, RL_MUTED),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_arch)
    story.append(PageBreak())

    # Slide 4: Directives
    story.append(Paragraph("SUPPORTED DIRECTIVES", style_category))
    story.append(Paragraph("Strict Semantic Normalization (6 Directive Types)", style_title))

    dirs = [
        [
            [Paragraph("solar_reduction", style_card_title), Paragraph("Usable solar multiplier (0.0 - 1.0).<br/><i>'80% solar reduction' → factor: 0.2</i>", style_body)],
            [Paragraph("minimum_battery_reserve", style_card_title_teal), Paragraph("Battery energy floor E[h] >= min.<br/><i>'Hold 80 kWh reserve' → min_energy: 80.0</i>", style_body)],
            [Paragraph("no_charge_window", style_card_title), Paragraph("Forced zero charge C[h] = 0.<br/><i>'No charging from 2-4 PM' → [14, 15]</i>", style_body)]
        ],
        [
            [Paragraph("no_discharge_window", style_card_title_teal), Paragraph("Forced zero discharge D[h] = 0.<br/><i>'Avoid discharge 6-8 PM' → [18, 19]</i>", style_body)],
            [Paragraph("max_grid_window", style_card_title), Paragraph("Grid import cap G[h] <= max.<br/><i>'Limit grid intake to 155 kWh' → 155.0</i>", style_body)],
            [Paragraph("no_op", style_card_title_teal), Paragraph("Informational or distractor notes.<br/><i>Applies = false, adjustment = null</i>", style_body)]
        ]
    ]

    t_dirs = Table([
        [dirs[0][0], dirs[0][1], dirs[0][2]],
        [dirs[1][0], dirs[1][1], dirs[1][2]]
    ], colWidths=[3.2 * inch, 3.2 * inch, 3.2 * inch])
    t_dirs.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), RL_CARD),
        ('BOX', (0, 0), (-1, -1), 1.2, RL_AMBER),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t_dirs)
    story.append(PageBreak())

    # Slide 5: Mathematical Formulation
    story.append(Paragraph("MATHEMATICAL OPTIMIZATION", style_category))
    story.append(Paragraph("Deterministic LP Formulation via HiGHS", style_title))

    f1 = [
        Paragraph("Optimization Objective & Dynamics", style_card_title_teal),
        Paragraph("• <b>Primary Objective:</b> min Σ (Grid[h] × Tariff[h]) for h = 0..23<br/>"
                  "• <b>Energy Balance:</b> Grid[h] + Solar[h] + Discharge[h] = Demand[h] + Charge[h]<br/>"
                  "• <b>Battery Transition:</b> E[h] = E[h-1] + Charge[h] - Discharge[h]<br/>"
                  "• <b>End-of-Day Neutrality:</b> E[23] == E_initial (Mandatory)", style_body)
    ]
    f2 = [
        Paragraph("Physical Constraints & Guarantees", style_card_title),
        Paragraph("• <b>Solar Curtailment:</b> 0 <= SolarUsed[h] <= EffectiveSolar[h]<br/>"
                  "• <b>Battery Limits:</b> min_reserve[h] <= E[h] <= capacity_kwh<br/>"
                  "• <b>Power Bounds:</b> 0 <= C[h] <= max_charge; 0 <= D[h] <= max_discharge<br/>"
                  "• <b>Execution:</b> HiGHS LP Solver (<50ms execution, deterministic)", style_body)
    ]

    t_form = Table([[f1, f2]], colWidths=[4.8 * inch, 4.8 * inch])
    t_form.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), RL_CARD),
        ('BOX', (0, 0), (0, 0), 1.2, RL_TEAL),
        ('BOX', (1, 0), (1, 0), 1.2, RL_AMBER),
        ('PADDING', (0, 0), (-1, -1), 14),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t_form)
    story.append(PageBreak())

    # Slide 6: Security & Cyber Defense
    story.append(Paragraph("SECURITY ARCHITECTURE", style_category))
    story.append(Paragraph("Enterprise Cyber Defense & Safe Fallback", style_title))

    sec_data = [
        [
            [Paragraph("Prompt Injection Defense", style_card_title_teal), Paragraph("Scans operator notes for adversarial patterns ('ignore instructions', 'reveal keys') and blocks suspicious requests.", style_body)],
            [Paragraph("LLM Circuit Breaker", style_card_title), Paragraph("CLOSED → OPEN → HALF_OPEN state machine isolates failing LLM APIs and activates safe fallback.", style_body)]
        ],
        [
            [Paragraph("Token-Bucket Rate Limiter", style_card_title), Paragraph("Per-client IP sliding window rate limiting (60 req/min + burst capacity) prevents DoS.", style_body)],
            [Paragraph("Sanitized Audit Logging", style_card_title_teal), Paragraph("SOC2-compliant structured JSON logs automatically redact API keys, tokens, and passwords.", style_body)]
        ]
    ]
    t_sec = Table([
        [sec_data[0][0], sec_data[0][1]],
        [sec_data[1][0], sec_data[1][1]]
    ], colWidths=[4.8 * inch, 4.8 * inch])
    t_sec.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), RL_CARD),
        ('BOX', (0, 0), (-1, -1), 1.2, RL_TEAL),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t_sec)
    story.append(PageBreak())

    # Slide 7: Verification & Benchmark Results
    story.append(Paragraph("TESTING & BENCHMARKS", style_category))
    story.append(Paragraph("100% Automated Test Pass Rate & Official Benchmarks", style_title))

    stats_col = [
        Paragraph("38 / 38", style_stat_val),
        Paragraph("Automated Tests Passed (100%)", style_stat_lbl),
        Spacer(1, 8),
        Paragraph("10 / 10", style_stat_val),
        Paragraph("Official BUP Challenge Cases Solved", style_stat_lbl),
        Spacer(1, 8),
        Paragraph("< 50 ms", style_stat_val),
        Paragraph("HiGHS Solver Execution Latency", style_stat_lbl),
        Spacer(1, 8),
        Paragraph("0.01 kWh", style_stat_val),
        Paragraph("Physical Replay Verification Tolerance", style_stat_lbl),
    ]

    tests_col = [
        Paragraph("Test Suite Breakdown", style_card_title),
        Paragraph("• <b>test_validation.py</b>: 24-hour array shapes, non-negativity, battery physics.<br/>"
                  "• <b>test_directives.py</b>: 6 directive types, simultaneous constraint composition.<br/>"
                  "• <b>test_llm_guardrails.py</b>: Injection defense, circuit breaker transitions.<br/>"
                  "• <b>test_optimizer.py</b>: HiGHS global optimality, battery neutrality, windows.<br/>"
                  "• <b>test_schedule_validator.py</b>: Independent physics replay, corruption detection.<br/>"
                  "• <b>test_security.py</b>: Rate limiting token bucket, IP quarantine, JWT auth.<br/>"
                  "• <b>test_public_cases.py</b>: Full integration with all official challenge scenarios.", style_body)
    ]

    t_results = Table([[stats_col, tests_col]], colWidths=[3.2 * inch, 6.4 * inch])
    t_results.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), RL_CARD),
        ('BOX', (0, 0), (0, 0), 1.2, RL_AMBER),
        ('BOX', (1, 0), (1, 0), 1.2, RL_TEAL),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t_results)
    story.append(PageBreak())

    # Slide 8: Conclusion & Impact
    story.append(Paragraph("CONCLUSION", style_category))
    story.append(Paragraph("GridWise: Production-Ready Campus Energy Intelligence", style_title))

    conc_box = [
        Paragraph("Key Takeaways for Judges", style_card_title),
        Paragraph("✔ <b>Deterministic Trust:</b> Mathematical optimization guarantees the global lowest-cost schedule with zero hallucination risk.<br/>"
                  "✔ <b>Complete Web Architecture:</b> Live interactive frontend console mounted seamlessly on FastAPI backend.<br/>"
                  "✔ <b>Enterprise Cyber Defense:</b> Token-bucket rate limiting, prompt-injection defense, circuit breaker, and audit logging.<br/>"
                  "✔ <b>Containerized & Reproducible:</b> Multi-stage Docker setup with non-root security and automatic health checks.<br/>"
                  "✔ <b>Scalability:</b> Adaptable to university campuses, hospital microgrids, EV fleet depots, and smart districts.", style_body),
        Spacer(1, 14),
        Paragraph("<b>Thank You! — KUET_CODE_AND_CAFFEINE</b>", style_card_title_teal)
    ]
    t_conc = Table([[conc_box]], colWidths=[9.8 * inch])
    t_conc.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), RL_CARD),
        ('BOX', (0, 0), (-1, -1), 1.5, RL_TEAL),
        ('PADDING', (0, 0), (-1, -1), 16),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t_conc)

    doc.build(story, onFirstPage=draw_bg, onLaterPages=draw_bg)
    print(f"PDF saved to {output_path}")


if __name__ == "__main__":
    docs_dir = os.path.join(os.path.dirname(__file__), "docs")
    os.makedirs(docs_dir, exist_ok=True)

    pptx_file = os.path.join(docs_dir, "GridWise_Presentation.pptx")
    pdf_file = os.path.join(docs_dir, "GridWise_Presentation.pdf")

    print("Generating PPTX...")
    create_pptx(pptx_file)

    print("Generating PDF...")
    create_pdf(pdf_file)

    print("Done! Both presentations generated in docs/")
