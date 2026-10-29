#!/usr/bin/env python3
"""
Adaptive Resource Quarantine - Review 1 PowerPoint Generator
Generates exact 10-slide PowerPoint presentation matching the design,
color palette (#F4EFEA background, #8C532B terracotta accents, #235347 forest green, #1C1917 typography),
and slide structure for Project Review 1.
"""

import os
import zipfile
import html

# Palette definition matching provided PPTX
COLOR_BG = "F4EFEA"          # Warm cream background
COLOR_TEXT_PRIMARY = "1C1917" # Charcoal / near black
COLOR_TEXT_MUTED = "57534E"   # Medium gray / brown
COLOR_ACCENT = "8C532B"       # Warm terracotta / bronze
COLOR_ACCENT_DARK = "693818"  # Dark bronze
COLOR_GREEN = "235347"        # Forest green highlight
COLOR_GREEN_LIGHT = "D5E5E0"  # Soft mint green
COLOR_CARD_BG = "FAF6F0"      # Light cream card
COLOR_CARD_BORDER = "DDD4C8"  # Soft border
COLOR_CARD_WHITE = "FFFFFF"   # Pure white card
COLOR_YELLOW_CARD = "F3ECDC"  # Soft beige warning card
COLOR_HEADER_BG = "8C532B"    # Brown table header
COLOR_HEADER_GREEN = "235347" # Green table header
COLOR_ROW_ALT = "F7F3EE"      # Alternating row background

def emu(val):
    """Convert inches or cm or points to EMUs if needed, or pass through."""
    return int(val)

# Slide dimensions (16:9 widescreen: 13.333 x 7.5 inches)
SLIDE_W = 12192000
SLIDE_H = 6858000

class SlideBuilder:
    def __init__(self, slide_num):
        self.slide_num = slide_num
        self.shape_id = 2
        self.shapes_xml = []

    def _next_id(self):
        self.shape_id += 1
        return self.shape_id

    def add_card(self, x, y, cx, cy, fill_color=COLOR_CARD_WHITE, border_color=COLOR_CARD_BORDER, border_width=12700, radius=None):
        sid = self._next_id()
        geom = 'roundRect' if radius is not False else 'rect'
        stroke_xml = f'<a:ln w="{border_width}"><a:solidFill><a:srgbClr val="{border_color}"/></a:solidFill></a:ln>' if border_color else '<a:ln><a:noFill/></a:ln>'
        xml = f'''<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="{sid}" name="Card {sid}"/>
    <p:cNvSpPr/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
    <a:prstGeom prst="{geom}"><a:avLst/></a:prstGeom>
    <a:solidFill><a:srgbClr val="{fill_color}"/></a:solidFill>
    {stroke_xml}
  </p:spPr>
</p:sp>'''
        self.shapes_xml.append(xml)
        return sid

    def add_textbox(self, x, y, cx, cy, paragraphs, anchor="t"):
        """
        paragraphs is a list of tuples or lists of runs:
        [
           # paragraph 1
           [
              {"text": "...", "sz": 1800, "b": True, "color": "1C1917", "italic": False, "font": "Georgia"},
              ...
           ],
           ...
        ]
        """
        sid = self._next_id()
        paras_xml = []
        for p in paragraphs:
            align = "l"
            bullet = ""
            runs_data = p
            if isinstance(p, dict):
                align = p.get("align", "l")
                runs_data = p.get("runs", [])
                if p.get("bullet"):
                    bullet = '<a:pPr marL="288000" indent="-288000"><a:buFont typeface="Arial"/><a:buChar char="•"/></a:pPr>'
            
            p_xml = [f'<a:p><a:pPr algn="{align}"/>{bullet}']
            for run in runs_data:
                txt = html.escape(run.get("text", ""))
                sz = run.get("sz", 1400)
                b = ' b="1"' if run.get("b") else ''
                it = ' i="1"' if run.get("italic") else ''
                color = run.get("color", COLOR_TEXT_PRIMARY)
                font = run.get("font", "Arial")
                p_xml.append(f'<a:r><a:rPr lang="en-US" sz="{sz}"{b}{it}><a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:latin typeface="{font}"/></a:rPr><a:t>{txt}</a:t></a:r>')
            p_xml.append('</a:p>')
            paras_xml.append("".join(p_xml))

        body_xml = "".join(paras_xml)
        xml = f'''<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="{sid}" name="TextBox {sid}"/>
    <p:cNvSpPr txBox="1"/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
    <a:noFill/>
  </p:spPr>
  <p:txBody>
    <a:bodyPr rtlCol="0" anchor="{anchor}" lIns="45720" tIns="45720" rIns="45720" bIns="45720"/>
    <a:lstStyle/>
    {body_xml}
  </p:txBody>
</p:sp>'''
        self.shapes_xml.append(xml)
        return sid

    def add_badge_circle(self, x, y, d, text, bg_color=COLOR_ACCENT, text_color="FFFFFF"):
        sid = self._next_id()
        xml = f'''<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="{sid}" name="Badge {sid}"/>
    <p:cNvSpPr/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{d}" cy="{d}"/></a:xfrm>
    <a:prstGeom prst="ellipse"><a:avLst/></a:prstGeom>
    <a:solidFill><a:srgbClr val="{bg_color}"/></a:solidFill>
    <a:ln><a:noFill/></a:ln>
  </p:spPr>
  <p:txBody>
    <a:bodyPr rtlCol="0" anchor="ctr" lIns="0" tIns="0" rIns="0" bIns="0"/>
    <a:lstStyle/>
    <a:p>
      <a:pPr algn="ctr"/>
      <a:r>
        <a:rPr lang="en-US" sz="1400" b="1"><a:solidFill><a:srgbClr val="{text_color}"/></a:solidFill><a:latin typeface="Arial"/></a:rPr>
        <a:t>{html.escape(str(text))}</a:t>
      </a:r>
    </a:p>
  </p:txBody>
</p:sp>'''
        self.shapes_xml.append(xml)
        return sid

    def add_table(self, x, y, cx, cy, headers, rows, col_widths, header_bg=COLOR_HEADER_BG, header_text="FFFFFF"):
        sid = self._next_id()
        # build grid
        grid_xml = "".join([f'<a:gridCol w="{w}"/>' for w in col_widths])
        
        # header row
        h_cells = []
        for h in headers:
            h_cells.append(f'''<a:tc>
  <a:txBody>
    <a:bodyPr anchor="ctr" lIns="72000" tIns="72000" rIns="72000" bIns="72000"/>
    <a:lstStyle/>
    <a:p><a:r><a:rPr sz="1200" b="1"><a:solidFill><a:srgbClr val="{header_text}"/></a:solidFill><a:latin typeface="Arial"/></a:rPr><a:t>{html.escape(h)}</a:t></a:r></a:p>
  </a:txBody>
  <a:tcPr>
    <a:solidFill><a:srgbClr val="{header_bg}"/></a:solidFill>
  </a:tcPr>
</a:tc>''')
        tr_h = f'<a:tr h="400000">{"".join(h_cells)}</a:tr>'
        
        # rows
        trs = [tr_h]
        for idx, row in enumerate(rows):
            r_cells = []
            bg = COLOR_ROW_ALT if idx % 2 == 1 else "FFFFFF"
            for c_idx, cell in enumerate(row):
                b_flag = ' b="1"' if c_idx == 0 else ''
                col_txt = COLOR_TEXT_PRIMARY if c_idx > 0 else COLOR_ACCENT_DARK
                r_cells.append(f'''<a:tc>
  <a:txBody>
    <a:bodyPr anchor="t" lIns="72000" tIns="54000" rIns="72000" bIns="54000"/>
    <a:lstStyle/>
    <a:p><a:r><a:rPr sz="1050"{b_flag}><a:solidFill><a:srgbClr val="{col_txt}"/></a:solidFill><a:latin typeface="Arial"/></a:rPr><a:t>{html.escape(str(cell))}</a:t></a:r></a:p>
  </a:txBody>
  <a:tcPr>
    <a:solidFill><a:srgbClr val="{bg}"/></a:solidFill>
    <a:lnL w="6350"><a:solidFill><a:srgbClr val="{COLOR_CARD_BORDER}"/></a:solidFill></a:lnL>
    <a:lnR w="6350"><a:solidFill><a:srgbClr val="{COLOR_CARD_BORDER}"/></a:solidFill></a:lnR>
    <a:lnT w="6350"><a:solidFill><a:srgbClr val="{COLOR_CARD_BORDER}"/></a:solidFill></a:lnT>
    <a:lnB w="6350"><a:solidFill><a:srgbClr val="{COLOR_CARD_BORDER}"/></a:solidFill></a:lnB>
  </a:tcPr>
</a:tc>''')
            trs.append(f'<a:tr h="600000">{"".join(r_cells)}</a:tr>')
            
        tbl_xml = f'''<p:graphicFrame>
  <p:nvGraphicFramePr>
    <p:cNvPr id="{sid}" name="Table {sid}"/>
    <p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr>
    <p:nvPr/>
  </p:nvGraphicFramePr>
  <p:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></p:xfrm>
  <a:graphic>
    <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">
      <a:tbl>
        <a:tblPr/>
        <a:tblGrid>{grid_xml}</a:tblGrid>
        {"".join(trs)}
      </a:tbl>
    </a:graphicData>
  </a:graphic>
</p:graphicFrame>'''
        self.shapes_xml.append(tbl_xml)
        return sid

    def add_header_and_footer(self, section_name, subtitle):
        # Section Category (e.g. PROJECT REVIEW 1 or LITERATURE SURVEY)
        self.add_textbox(600000, 450000, 11000000, 320000, [
            [{"text": section_name.upper(), "sz": 1100, "b": True, "color": COLOR_ACCENT, "font": "Arial"}]
        ])
        # Subtitle / Slide Main Heading
        self.add_textbox(600000, 780000, 11000000, 600000, [
            [{"text": subtitle, "sz": 2200, "b": True, "color": COLOR_TEXT_PRIMARY, "font": "Georgia"}]
        ])
        # Footer
        self.add_textbox(600000, 6450000, 9000000, 250000, [
            [{"text": "Adaptive Resource Quarantine · Project Review 1", "sz": 950, "color": COLOR_TEXT_MUTED, "font": "Arial"}]
        ])
        # Slide number
        self.add_textbox(11200000, 6450000, 400000, 250000, [
            {"align": "r", "runs": [{"text": str(self.slide_num), "sz": 950, "color": COLOR_TEXT_MUTED, "font": "Arial"}]}
        ])

    def to_xml(self):
        shapes_body = "".join(self.shapes_xml)
        return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:bg>
      <p:bgPr>
        <a:solidFill><a:srgbClr val="{COLOR_BG}"/></a:solidFill>
      </p:bgPr>
    </p:bg>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      {shapes_body}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>'''

def build_presentation(output_path):
    slides = []

    # ==========================================
    # SLIDE 1: Title & Team Details
    # ==========================================
    s1 = SlideBuilder(1)
    s1.add_textbox(600000, 500000, 7000000, 320000, [
        [{"text": "PROJECT REVIEW 1", "sz": 1200, "b": True, "color": COLOR_ACCENT, "font": "Arial"}]
    ])
    s1.add_textbox(600000, 950000, 6800000, 1500000, [
        [{"text": "Adaptive Resource", "sz": 3800, "b": True, "color": COLOR_TEXT_PRIMARY, "font": "Georgia"}],
        [{"text": "Quarantine", "sz": 3800, "b": True, "color": COLOR_TEXT_PRIMARY, "font": "Georgia"}]
    ])
    s1.add_textbox(600000, 2600000, 6800000, 700000, [
        [{"text": "for Protecting Operating Systems Against Abnormal Process Behavior", "sz": 1600, "italic": True, "color": COLOR_ACCENT, "font": "Georgia"}]
    ])
    s1.add_textbox(600000, 3450000, 6800000, 900000, [
        [{"text": "A lightweight OS mechanism that scores abnormal process behavior and temporarily restricts its resources instead of killing it, then releases it once it recovers.", "sz": 1300, "color": COLOR_TEXT_PRIMARY, "font": "Arial"}]
    ])

    # Left Team Box
    s1.add_textbox(600000, 4600000, 6800000, 300000, [
        [{"text": "TEAM DETAILS", "sz": 1100, "b": True, "color": COLOR_ACCENT, "font": "Arial"}]
    ])
    s1.add_textbox(600000, 4950000, 6800000, 1350000, [
        [{"text": "Name: Rithika.s   Reg. No.: 24BCE2984  ·  B.Tech CSE", "sz": 1250, "b": True, "color": COLOR_TEXT_PRIMARY, "font": "Arial"}],
        [{"text": "Name: K.VAISHNAVI   Reg. No.: 24BCT0183  ·  B.Tech CSE IOT", "sz": 1250, "b": True, "color": COLOR_TEXT_PRIMARY, "font": "Arial"}],
        [{"text": "Lab slot: L15+16", "sz": 1200, "color": COLOR_TEXT_MUTED, "font": "Arial"}],
        [{"text": "Faculty: Dr. Anisha M Lal  ·  Department of Computer Science and Engineering", "sz": 1200, "color": COLOR_TEXT_PRIMARY, "font": "Arial"}]
    ])

    # Right Card: The Quarantine Loop
    s1.add_card(7800000, 750000, 3800000, 5400000, fill_color="FAF6F0", border_color=COLOR_CARD_BORDER)
    s1.add_textbox(8100000, 1000000, 3200000, 300000, [
        [{"text": "THE QUARANTINE LOOP", "sz": 1100, "b": True, "color": COLOR_ACCENT, "font": "Arial"}]
    ])
    
    # 4 Steps in Loop
    loop_steps = [
        (1, "Monitor and score", "CPU, memory, I/O", COLOR_ACCENT),
        (2, "Quarantine", "Throttle, don't kill", COLOR_ACCENT),
        (3, "Re-evaluate", "Is behavior normal?", COLOR_ACCENT),
        (4, "Release or Terminate", "Recover, or end it", COLOR_GREEN),
    ]
    y_step = 1450000
    for num, title, desc, col in loop_steps:
        s1.add_badge_circle(8150000, y_step + 30000, 480000, num, bg_color=col, text_color="FFFFFF")
        s1.add_textbox(8750000, y_step, 2600000, 600000, [
            [{"text": title, "sz": 1350, "b": True, "color": COLOR_TEXT_PRIMARY, "font": "Georgia"}],
            [{"text": desc, "sz": 1100, "color": COLOR_TEXT_MUTED, "font": "Arial"}]
        ])
        y_step += 1100000

    s1.add_textbox(600000, 6450000, 9000000, 250000, [
        [{"text": "Adaptive Resource Quarantine · Project Review 1", "sz": 950, "color": COLOR_TEXT_MUTED, "font": "Arial"}]
    ])
    s1.add_textbox(11200000, 6450000, 400000, 250000, [
        {"align": "r", "runs": [{"text": "1", "sz": 950, "color": COLOR_TEXT_MUTED, "font": "Arial"}]}
    ])
    slides.append(s1)

    # ==========================================
    # SLIDE 2: Abstract
    # ==========================================
    s2 = SlideBuilder(2)
    s2.add_header_and_footer("ABSTRACT", "Restrict first, terminate only if needed")
    
    # Left Box (Big Card)
    s2.add_card(600000, 1500000, 6800000, 4650000, fill_color="FFFFFF", border_color=COLOR_CARD_BORDER)
    s2.add_textbox(850000, 1750000, 6300000, 4150000, [
        [{"text": "Modern operating systems run many processes at once, and abnormal resource consumption by a single process can significantly affect overall performance and stability.", "sz": 1350, "color": COLOR_TEXT_PRIMARY, "font": "Arial"}],
        [{"text": "", "sz": 600}],
        [{"text": "This project proposes an Adaptive Resource Quarantine mechanism that continuously monitors CPU utilization, memory consumption, I/O activity and execution patterns. A process that behaves abnormally receives an anomaly score and has its resource access temporarily restricted, rather than being terminated immediately.", "sz": 1350, "color": COLOR_TEXT_PRIMARY, "font": "Arial"}],
        [{"text": "", "sz": 600}],
        [{"text": "CPU priority, memory usage and I/O access are controlled dynamically during quarantine. The process is released when its behavior returns to normal, or terminated if the abnormal behavior persists.", "sz": 1350, "color": COLOR_TEXT_PRIMARY, "font": "Arial"}],
        [{"text": "", "sz": 600}],
        [{"text": "The goal is lightweight process isolation that preserves system availability and limits the impact of resource-intensive or potentially malicious processes.", "sz": 1350, "color": COLOR_TEXT_PRIMARY, "font": "Arial"}]
    ])

    # Right Cards (3 Stacked)
    right_cards = [
        ("Anomaly score", "Multi-metric, not a single threshold.", "FFFFFF"),
        ("Graduated restriction", "CPU priority, memory and I/O controlled together.", "FFFFFF"),
        ("Release or terminate", "Recover on normal behavior; end it if abnormal behavior persists.", "FFFFFF"),
    ]
    y_rc = 1500000
    for title, desc, bg in right_cards:
        s2.add_card(7650000, y_rc, 3950000, 1400000, fill_color=bg, border_color=COLOR_CARD_BORDER)
        s2.add_textbox(7900000, y_rc + 250000, 3450000, 950000, [
            [{"text": title, "sz": 1500, "b": True, "color": COLOR_TEXT_PRIMARY, "font": "Georgia"}],
            [{"text": desc, "sz": 1200, "color": COLOR_TEXT_MUTED, "font": "Arial"}]
        ])
        y_rc += 1625000
    slides.append(s2)

    # ==========================================
    # SLIDE 3: Introduction: Context and Problem
    # ==========================================
    s3 = SlideBuilder(3)
    s3.add_header_and_footer("INTRODUCTION: CONTEXT AND PROBLEM", "One runaway process should not take the system down")

    # Left Column: Bullets
    bullets = [
        ("Shared resources, shared fate.", " Processes compete for the same CPU, memory and I/O, so one misbehaving process can degrade or destabilize all the others."),
        ("Killing is blunt.", " Terminating a process loses its state, and can kill a legitimate workload that was only busy."),
        ("Static caps are rigid.", " Fixed limits cannot separate a short burst from sustained abuse, and rarely scale back up on their own."),
    ]
    y_b = 1600000
    for head, text in bullets:
        s3.add_textbox(600000, y_b, 5000000, 1200000, [
            {"bullet": True, "runs": [
                {"text": head, "sz": 1350, "b": True, "color": COLOR_TEXT_PRIMARY, "font": "Arial"},
                {"text": text, "sz": 1350, "color": COLOR_TEXT_PRIMARY, "font": "Arial"}
            ]}
        ])
        y_b += 1400000

    # Right Card: Flow Comparison
    s3.add_card(5850000, 1500000, 5750000, 4650000, fill_color="FAF6F0", border_color=COLOR_CARD_BORDER)
    
    # Today Flow
    s3.add_textbox(6100000, 1750000, 5200000, 250000, [
        [{"text": "TODAY: STATIC CAP OR KILL", "sz": 1050, "b": True, "color": COLOR_ACCENT, "font": "Arial"}]
    ])
    # boxes
    s3.add_card(6100000, 2100000, 1400000, 750000, fill_color="FFFFFF", border_color=COLOR_CARD_BORDER)
    s3.add_textbox(6150000, 2250000, 1300000, 500000, [{"align": "ctr", "runs": [{"text": "Process\nmisbehaves", "sz": 1000, "b": True, "color": COLOR_TEXT_PRIMARY}]}])
    
    s3.add_textbox(7500000, 2300000, 300000, 350000, [{"align": "ctr", "runs": [{"text": "→", "sz": 1600, "color": COLOR_TEXT_MUTED}]}])

    s3.add_card(7800000, 2100000, 1400000, 750000, fill_color="FFFFFF", border_color=COLOR_CARD_BORDER)
    s3.add_textbox(7850000, 2250000, 1300000, 500000, [{"align": "ctr", "runs": [{"text": "Threshold\ncrossed", "sz": 1000, "b": True, "color": COLOR_TEXT_PRIMARY}]}])

    s3.add_textbox(9200000, 2300000, 300000, 350000, [{"align": "ctr", "runs": [{"text": "→", "sz": 1600, "color": COLOR_TEXT_MUTED}]}])

    s3.add_card(9500000, 2100000, 1700000, 750000, fill_color=COLOR_YELLOW_CARD, border_color="D6C9B0")
    s3.add_textbox(9550000, 2320000, 1600000, 450000, [{"align": "ctr", "runs": [{"text": "Cap or kill", "sz": 1100, "b": True, "color": COLOR_ACCENT_DARK}]}])

    # Proposed Flow
    s3.add_textbox(6100000, 3200000, 5200000, 250000, [
        [{"text": "PROPOSED: ADAPTIVE QUARANTINE", "sz": 1050, "b": True, "color": COLOR_ACCENT, "font": "Arial"}]
    ])
    s3.add_card(6100000, 3550000, 1050000, 750000, fill_color="FFFFFF", border_color=COLOR_CARD_BORDER)
    s3.add_textbox(6120000, 3770000, 1010000, 450000, [{"align": "ctr", "runs": [{"text": "Monitor", "sz": 1050, "b": True, "color": COLOR_TEXT_PRIMARY}]}])

    s3.add_textbox(7150000, 3750000, 250000, 350000, [{"align": "ctr", "runs": [{"text": "→", "sz": 1500, "color": COLOR_TEXT_MUTED}]}])

    s3.add_card(7400000, 3550000, 1050000, 750000, fill_color="FFFFFF", border_color=COLOR_CARD_BORDER)
    s3.add_textbox(7420000, 3770000, 1010000, 450000, [{"align": "ctr", "runs": [{"text": "Score", "sz": 1050, "b": True, "color": COLOR_TEXT_PRIMARY}]}])

    s3.add_textbox(8450000, 3750000, 250000, 350000, [{"align": "ctr", "runs": [{"text": "→", "sz": 1500, "color": COLOR_TEXT_MUTED}]}])

    s3.add_card(8700000, 3550000, 1200000, 750000, fill_color="FFFFFF", border_color=COLOR_CARD_BORDER)
    s3.add_textbox(8720000, 3770000, 1160000, 450000, [{"align": "ctr", "runs": [{"text": "Quarantine", "sz": 1050, "b": True, "color": COLOR_TEXT_PRIMARY}]}])

    s3.add_textbox(9900000, 3750000, 250000, 350000, [{"align": "ctr", "runs": [{"text": "→", "sz": 1500, "color": COLOR_TEXT_MUTED}]}])

    s3.add_card(10150000, 3550000, 1250000, 750000, fill_color=COLOR_GREEN, border_color=COLOR_GREEN)
    s3.add_textbox(10170000, 3770000, 1210000, 450000, [{"align": "ctr", "runs": [{"text": "Release / End", "sz": 1050, "b": True, "color": "FFFFFF"}]}])

    # Caption bottom of proposed card
    s3.add_textbox(6100000, 4850000, 5200000, 900000, [
        [{"text": "The proposed loop is closed: behavior is re-scored during quarantine, so restriction eases or tightens with the process.", "sz": 1200, "italic": True, "color": COLOR_TEXT_MUTED, "font": "Georgia"}]
    ])
    slides.append(s3)

    # ==========================================
    # SLIDE 4: Introduction: Objectives
    # ==========================================
    s4 = SlideBuilder(4)
    s4.add_header_and_footer("INTRODUCTION: OBJECTIVES", "Seven measurable objectives")

    objectives = [
        (1, "Continuous monitoring", "Track CPU, memory and I/O usage of running processes."),
        (2, "Anomaly scoring", "Identify abnormal behavior from consumption patterns."),
        (3, "Adaptive quarantine", "Temporarily restrict resources of abnormal processes."),
        (4, "Protect other processes", "Stop one process from degrading the rest."),
        (5, "Dynamic restoration", "Restore normal allocation once behavior recovers."),
        (6, "Evaluation", "CPU utilization, memory, response time, I/O, recovery time."),
        (7, "Lightweight alternative", "Avoid immediately terminating abnormal processes."),
    ]

    card_w = 2650000
    card_h = 2150000
    start_x = 600000
    gap_x = 150000
    
    # Row 1: 1, 2, 3, 4
    for i in range(4):
        num, title, desc = objectives[i]
        cx = start_x + i * (card_w + gap_x)
        cy = 1600000
        s4.add_card(cx, cy, card_w, card_h, fill_color="FFFFFF", border_color=COLOR_CARD_BORDER)
        s4.add_badge_circle(cx + 200000, cy + 200000, 350000, num, bg_color=COLOR_ACCENT)
        s4.add_textbox(cx + 200000, cy + 700000, card_w - 400000, 500000, [
            [{"text": title, "sz": 1350, "b": True, "color": COLOR_TEXT_PRIMARY, "font": "Georgia"}]
        ])
        s4.add_textbox(cx + 200000, cy + 1250000, card_w - 400000, 800000, [
            [{"text": desc, "sz": 1150, "color": COLOR_TEXT_MUTED, "font": "Arial"}]
        ])

    # Row 2: 5, 6, 7, and Core Idea Box
    # 5, 6, 7
    for i in range(4, 7):
        num, title, desc = objectives[i]
        cx = start_x + (i - 4) * (card_w + gap_x)
        cy = 3950000
        s4.add_card(cx, cy, card_w, card_h, fill_color="FFFFFF", border_color=COLOR_CARD_BORDER)
        s4.add_badge_circle(cx + 200000, cy + 200000, 350000, num, bg_color=COLOR_ACCENT)
        s4.add_textbox(cx + 200000, cy + 700000, card_w - 400000, 500000, [
            [{"text": title, "sz": 1350, "b": True, "color": COLOR_TEXT_PRIMARY, "font": "Georgia"}]
        ])
        s4.add_textbox(cx + 200000, cy + 1250000, card_w - 400000, 800000, [
            [{"text": desc, "sz": 1150, "color": COLOR_TEXT_MUTED, "font": "Arial"}]
        ])

    # Core Idea Green Box in 4th slot of Row 2
    cx = start_x + 3 * (card_w + gap_x)
    cy = 3950000
    s4.add_card(cx, cy, card_w, card_h, fill_color=COLOR_GREEN, border_color=COLOR_GREEN)
    s4.add_textbox(cx + 220000, cy + 250000, card_w - 440000, 300000, [
        [{"text": "CORE IDEA", "sz": 1050, "b": True, "color": COLOR_GREEN_LIGHT, "font": "Arial"}]
    ])
    s4.add_textbox(cx + 220000, cy + 700000, card_w - 440000, 1200000, [
        [{"text": "Restrict, don't kill.", "sz": 1700, "b": True, "color": "FFFFFF", "font": "Georgia"}],
        [{"text": "Release on", "sz": 1700, "b": True, "color": "FFFFFF", "font": "Georgia"}],
        [{"text": "recovery.", "sz": 1700, "b": True, "color": "FFFFFF", "font": "Georgia"}]
    ])
    slides.append(s4)

    # ==========================================
    # SLIDE 5: Literature Survey: Detecting Abnormal Behavior
    # ==========================================
    s5 = SlideBuilder(5)
    s5.add_header_and_footer("LITERATURE SURVEY: DETECTING ABNORMAL BEHAVIOR", "Detection is well studied, but stops at flagging")
    
    headers_lit = ["Work", "Technique", "Limitation / key finding"]
    col_w_lit = [3200000, 3500000, 4300000]
    rows_lit1 = [
        [
            "Ibidunmoye et al., ACM Computing Surveys, 2015\nPerformance Anomaly Detection and Bottleneck Identification",
            "Surveys detection goals, application types, observability and methods for performance anomalies.",
            "Shows the problem is hard and varied, with contention across CPU, memory, disk and network. A survey, so it prescribes no process-level response."
        ],
        [
            "Zhang et al., AIPR, 2023\nAnomaly Detection Model for Process Resource Usage ... eBPF and Isolation Forest",
            "eBPF collects process-level resource telemetry; Isolation Forest flags anomalous usage.",
            "Detection-focused. The reported design has no throttling, quarantine or release step."
        ],
        [
            "Ma et al., CCC, 2025\nMemory Anomaly Detection and Analysis Based on eBPF and Isolation Forest",
            "Detects and locates potential memory anomalies in the operating system.",
            "Memory only, and meant as a diagnostic aid for developers rather than an automatic control."
        ],
        [
            "Szabo et al., IEEE TDSC, 2020\nAdaptive Performance Anomaly Detection in Distributed Systems Using Online SVMs",
            "Online SVMs learn without historical failure data; F-score above 0.70 on unseen anomalies.",
            "Aimed at distributed systems. Flags anomalies but does not control the offending process."
        ]
    ]
    s5.add_table(600000, 1600000, 11000000, 4500000, headers_lit, rows_lit1, col_w_lit, header_bg=COLOR_HEADER_BG)
    slides.append(s5)

    # ==========================================
    # SLIDE 6: Literature Survey: Containing Abnormal Behavior
    # ==========================================
    s6 = SlideBuilder(6)
    s6.add_header_and_footer("LITERATURE SURVEY: CONTAINING ABNORMAL BEHAVIOR", "Containment works, but release is rarely addressed")
    
    rows_lit2 = [
        [
            "Somayaji, 2002\nOperating system stability and security through process homeostasis (pH)",
            "Linux kernel extension detects unusual program behavior and slows it by delaying system calls.",
            "Few-percent performance penalty and low false positives, but slowdown acts through system calls, not direct CPU, memory and I/O allocation."
        ],
        [
            "Nakagawa et al., IEEE, 2015\nOn-the-Fly Process Resource Quarantine for System Stabilization",
            "Assigns dynamic kernel or cgroup limits after periodic inspection; targets memory limits and fork-bomb suppression.",
            "Closest prior work. Centered on memory limits, with no multi-metric anomaly score or formal release policy."
        ],
        [
            "Chen et al., SC20, 2020\nAlita: Comprehensive Performance Isolation through Bias Resource Management",
            "Identifies resource polluters online and throttles only them; tested on a 30,000-node cloud platform.",
            "Works at VM and cloud level, not per-process inside a single OS. Release logic is not its focus."
        ],
        [
            "Wang et al., FGCS, 2022\nCharacterizing and optimizing Kernel resource isolation for containers (Valve)",
            "Limits misbehaving system-call usage; up to 98% (average 37.7%) isolation improvement.",
            "Container-level kernel-object isolation, with no anomaly scoring or release step."
        ]
    ]
    s6.add_table(600000, 1600000, 11000000, 4500000, headers_lit, rows_lit2, col_w_lit, header_bg=COLOR_HEADER_BG)
    slides.append(s6)

    # ==========================================
    # SLIDE 7: Literature Survey: What the Evidence Says
    # ==========================================
    s7 = SlideBuilder(7)
    s7.add_header_and_footer("LITERATURE SURVEY: WHAT THE EVIDENCE SAYS", "Adaptive isolation helps, so it is worth building well")

    stat_cards = [
        ("9 of 9", "papers that took a stance say adaptive quarantine reduces system-wide degradation.", "Consensus Meter, N = 9"),
        ("66%", "average CPU utilization, up from 21%, on 90,000+ Bing servers with no harm to tail latency.", "PerfIso, 2018"),
        ("98%", "maximum kernel resource isolation improvement by limiting misbehaving system calls.", "Valve, 2022"),
        ("6.9 s", "recovery time ceiling after container out-of-memory events, even with multiple attackers.", "ROMA, 2026"),
    ]
    stat_w = 2650000
    stat_h = 2600000
    for idx, (num, text, cite) in enumerate(stat_cards):
        cx = 600000 + idx * (stat_w + 130000)
        cy = 1600000
        s7.add_card(cx, cy, stat_w, stat_h, fill_color="FFFFFF", border_color=COLOR_CARD_BORDER)
        s7.add_textbox(cx + 200000, cy + 250000, stat_w - 400000, 800000, [
            [{"text": num, "sz": 3200, "b": True, "color": COLOR_ACCENT, "font": "Georgia"}]
        ])
        s7.add_textbox(cx + 200000, cy + 1150000, stat_w - 400000, 950000, [
            [{"text": text, "sz": 1150, "color": COLOR_TEXT_PRIMARY, "font": "Arial"}]
        ])
        s7.add_textbox(cx + 200000, cy + 2150000, stat_w - 400000, 300000, [
            [{"text": cite, "sz": 1000, "color": COLOR_TEXT_MUTED, "font": "Arial"}]
        ])

    # The Catch Bottom Card
    s7.add_card(600000, 4450000, 11000000, 1600000, fill_color=COLOR_YELLOW_CARD, border_color="D6C9B0")
    s7.add_textbox(900000, 4650000, 10400000, 250000, [
        [{"text": "THE CATCH", "sz": 1050, "b": True, "color": COLOR_ACCENT, "font": "Arial"}]
    ])
    s7.add_textbox(900000, 4950000, 10400000, 850000, [
        [{"text": "Most of this work covers detection and mitigation. Very few studies evaluate how a restricted process is safely released once it behaves normally, and poorly tuned throttling can still cost throughput.", "sz": 1250, "color": COLOR_TEXT_PRIMARY, "font": "Arial"}]
    ])
    slides.append(s7)

    # ==========================================
    # SLIDE 8: Gaps of Existing Systems
    # ==========================================
    s8 = SlideBuilder(8)
    s8.add_header_and_footer("GAPS OF EXISTING SYSTEMS", "Four gaps that no single system closes")

    gaps = [
        ("01", "Release is under-studied", "Detection and mitigation are well developed, but automated restoration is largely unexplored. Many designs keep static throttling or need an administrator once a threshold is crossed."),
        ("02", "Static, single-signal thresholds", "Fixed thresholds raise false alarms on bursty workloads, and static caps can throttle unnecessarily, as shown in Linux CFS bandwidth control."),
        ("03", "Cross-resource blind spots", "Memory limits alone were not enough in Meta's datacenters: reclaim still interfered through I/O. CPU, memory and I/O need joint control."),
        ("04", "Detection and control are disconnected", "eBPF and Isolation Forest detectors only flag; enforcement systems act on thresholds. A process-level loop from score to restriction to release is missing.")
    ]
    gap_w = 5350000
    gap_h = 2200000
    positions = [
        (600000, 1650000),
        (6250000, 1650000),
        (600000, 4050000),
        (6250000, 4050000),
    ]
    for idx, (num, title, desc) in enumerate(gaps):
        gx, gy = positions[idx]
        s8.add_card(gx, gy, gap_w, gap_h, fill_color="FFFFFF", border_color=COLOR_CARD_BORDER)
        # Big number
        s8.add_textbox(gx + 250000, gy + 200000, 750000, 500000, [
            [{"text": num, "sz": 2200, "b": True, "color": COLOR_ACCENT, "font": "Georgia"}]
        ])
        # Title
        s8.add_textbox(gx + 1050000, gy + 250000, gap_w - 1300000, 450000, [
            [{"text": title, "sz": 1450, "b": True, "color": COLOR_TEXT_PRIMARY, "font": "Georgia"}]
        ])
        # Description
        s8.add_textbox(gx + 250000, gy + 850000, gap_w - 500000, 1150000, [
            [{"text": desc, "sz": 1200, "color": COLOR_TEXT_MUTED, "font": "Arial"}]
        ])
    slides.append(s8)

    # ==========================================
    # SLIDE 9: Gaps of Existing Systems: Comparison
    # ==========================================
    s9 = SlideBuilder(9)
    s9.add_header_and_footer("GAPS OF EXISTING SYSTEMS: COMPARISON", "The proposed mechanism closes the loop")

    comp_headers = ["Feature", "Nakagawa 2015", "pH (Somayaji)", "Alita (Chen 2020)", "eBPF + IF (Zhang 2023)", "Proposed"]
    comp_col_w = [1800000, 2000000, 2000000, 2000000, 2000000, 2200000]
    comp_rows = [
        ["Signals monitored", "Memory, fork activity", "System-call sequences", "Shared-resource pollution", "CPU, memory, I/O", "CPU, memory, I/O, execution patterns"],
        ["Anomaly detection", "Periodic inspection", "Short-range system-call baselines", "Online polluter identification", "Isolation Forest", "Composite anomaly score"],
        ["Response", "Dynamic limits", "System-call delays", "Throttle polluters", "None (detection only)", "Graduated CPU, memory and I/O restriction"],
        ["Release / recovery", "Not evaluated", "Not evaluated", "Not evaluated", "Not applicable", "Auto-release on recovery, terminate if persistent"],
        ["Granularity", "Process", "Process", "VM", "Process", "Process"]
    ]
    s9.add_table(600000, 1600000, 11000000, 4300000, comp_headers, comp_rows, comp_col_w, header_bg=COLOR_GREEN)
    s9.add_textbox(600000, 6050000, 11000000, 300000, [
        [{"text": "Entries are drawn from each work's published abstract and a literature-search summary; marked 'Not evaluated' where release was not reported.", "sz": 950, "italic": True, "color": COLOR_TEXT_MUTED, "font": "Arial"}]
    ])
    slides.append(s9)

    # ==========================================
    # SLIDE 10: Summary and Next Steps
    # ==========================================
    s10 = SlideBuilder(10)
    s10.add_header_and_footer("SUMMARY AND NEXT STEPS", "A lightweight, reversible response to abnormal processes")

    sum_w = 3530000
    sum_h = 3200000
    s_cards = [
        ("THE PROBLEM", "One abnormal process can degrade or destabilize a whole OS, and the usual answers are to kill it or cap it statically.", "FFFFFF", COLOR_CARD_BORDER),
        ("THE GAP", "Detection and throttling are mature, but few systems link multi-metric scoring to graduated restriction and a safe release.", "FFFFFF", COLOR_CARD_BORDER),
        ("PROPOSED", "Monitor CPU, memory and I/O, score anomalies, quarantine adaptively, then release on recovery or terminate if abnormal behavior persists.", "FAF6F0", COLOR_ACCENT)
    ]
    for idx, (title, desc, bg, border) in enumerate(s_cards):
        cx = 600000 + idx * (sum_w + 205000)
        cy = 1600000
        s10.add_card(cx, cy, sum_w, sum_h, fill_color=bg, border_color=border)
        s10.add_textbox(cx + 250000, cy + 300000, sum_w - 500000, 300000, [
            [{"text": title, "sz": 1100, "b": True, "color": COLOR_ACCENT, "font": "Arial"}]
        ])
        s10.add_textbox(cx + 250000, cy + 850000, sum_w - 500000, 1800000, [
            [{"text": desc, "sz": 1350, "color": COLOR_TEXT_PRIMARY, "font": "Arial"}]
        ])

    # Next Review 2 Banner
    s10.add_card(600000, 5050000, 11000000, 1150000, fill_color=COLOR_YELLOW_CARD, border_color="D6C9B0")
    s10.add_textbox(900000, 5200000, 10400000, 250000, [
        [{"text": "NEXT: REVIEW 2", "sz": 1050, "b": True, "color": COLOR_ACCENT, "font": "Arial"}]
    ])
    s10.add_textbox(900000, 5500000, 10400000, 500000, [
        [{"text": "Proposed methodology  ·  System architecture  ·  Outputs", "sz": 1600, "b": True, "color": COLOR_TEXT_PRIMARY, "font": "Georgia"}]
    ])
    slides.append(s10)

    # ==========================================
    # Package into PPTX ZIP Archive
    # ==========================================
    # XML definitions for OpenXML presentation packaging
    types_xml = ['''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>''']
    for i in range(1, len(slides) + 1):
        types_xml.append(f'  <Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>')
    types_xml.append('</Types>')

    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>'''

    pres_sld_ids = []
    pres_rels_items = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>',
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>'
    ]
    for i in range(1, len(slides) + 1):
        rel_id = f"rId{i + 2}"
        pres_sld_ids.append(f'<p:sldId id="{255 + i}" r:id="{rel_id}"/>')
        pres_rels_items.append(f'<Relationship Id="{rel_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>')

    pres_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst>
    <p:sldMasterId id="2147483648" r:id="rId1"/>
  </p:sldMasterIdLst>
  <p:sldIdLst>
    {"".join(pres_sld_ids)}
  </p:sldIdLst>
  <p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>'''

    pres_rels = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {"".join(pres_rels_items)}
</Relationships>'''

    theme_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Adaptive Resource Theme">
  <a:themeElements>
    <a:clrScheme name="ARQ_Warm">
      <a:dk1><a:srgbClr val="{COLOR_TEXT_PRIMARY}"/></a:dk1>
      <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="{COLOR_ACCENT_DARK}"/></a:dk2>
      <a:lt2><a:srgbClr val="{COLOR_BG}"/></a:lt2>
      <a:accent1><a:srgbClr val="{COLOR_ACCENT}"/></a:accent1>
      <a:accent2><a:srgbClr val="{COLOR_GREEN}"/></a:accent2>
      <a:accent3><a:srgbClr val="4682B4"/></a:accent3>
      <a:accent4><a:srgbClr val="D4AF37"/></a:accent4>
      <a:accent5><a:srgbClr val="708090"/></a:accent5>
      <a:accent6><a:srgbClr val="CD853F"/></a:accent6>
      <a:hlink><a:srgbClr val="0066CC"/></a:hlink>
      <a:folHlink><a:srgbClr val="800080"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="ARQ_Fonts">
      <a:majorFont><a:latin typeface="Georgia"/></a:majorFont>
      <a:minorFont><a:latin typeface="Arial"/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="Office">
      <a:fillStyleLst><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:fillStyleLst>
      <a:lnStyleLst><a:ln w="9525"><a:solidFill><a:srgbClr val="CCCCCC"/></a:solidFill></a:ln></a:lnStyleLst>
      <a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
      <a:bgFillStyleLst><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:bgFillStyleLst>
    </a:fmtScheme>
  </a:themeElements>
</a:theme>'''

    master_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst>
    <p:sldLayoutId id="2147483649" r:id="rId1"/>
  </p:sldLayoutIdLst>
</p:sldMaster>'''

    master_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>'''

    layout_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank">
  <p:cSld name="Blank">
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>'''

    layout_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>'''

    slide_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>'''

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', "\n".join(types_xml))
        z.writestr('_rels/.rels', root_rels)
        z.writestr('ppt/presentation.xml', pres_xml)
        z.writestr('ppt/_rels/presentation.xml.rels', pres_rels)
        z.writestr('ppt/theme/theme1.xml', theme_xml)
        z.writestr('ppt/slideMasters/slideMaster1.xml', master_xml)
        z.writestr('ppt/slideMasters/_rels/slideMaster1.xml.rels', master_rels)
        z.writestr('ppt/slideLayouts/slideLayout1.xml', layout_xml)
        z.writestr('ppt/slideLayouts/_rels/slideLayout1.xml.rels', layout_rels)
        
        for idx, slide in enumerate(slides, start=1):
            z.writestr(f'ppt/slides/slide{idx}.xml', slide.to_xml())
            z.writestr(f'ppt/slides/_rels/slide{idx}.xml.rels', slide_rels)

    print(f"Successfully generated Review 1 PPTX ({len(slides)} slides) at: {output_path}")

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "Adaptive_Resource_Quarantine_Review_1.pptx")
    build_presentation(out)
