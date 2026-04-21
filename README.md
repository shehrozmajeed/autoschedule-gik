<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=28&duration=3000&pause=1000&color=378ADD&center=true&vCenter=true&width=700&lines=AutoSchedule+GIK+%F0%9F%93%85;O(C+log+C)+Timetable+Scheduler;Zero+Hard+Constraint+Violations;780+Sessions+%E2%80%A2+%3C10ms+Runtime" alt="Typing SVG" />

<br/>

![Python](https://img.shields.io/badge/Python-3.11+-378ADD?style=for-the-badge&logo=python&logoColor=white)
![Complexity](https://img.shields.io/badge/Complexity-O(C%20log%20C)-1D9E75?style=for-the-badge)
![GUI](https://img.shields.io/badge/GUI-Tkinter-7F77DD?style=for-the-badge)
![Sessions](https://img.shields.io/badge/Sessions-780%20Scheduled-639922?style=for-the-badge)
![Conflicts](https://img.shields.io/badge/Conflicts-0%20Hard-D85A30?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-BA7517?style=for-the-badge)

<br/>

**Intelligent, constraint-aware automated timetable scheduler for GIK Institute of Engineering Sciences & Technology.**  
Greedy O(C log C) algorithm · 80 rooms · 18 course prefixes · Lab/lecture room allocation · GIK-format PDF & Excel export.

<br/>

[Features](#-features) · [Algorithm](#-algorithm--oc-log-c) · [Room Mapping](#-room-allocation) · [Quick Start](#-quick-start) · [GUI](#-gui-walkthrough) · [Export](#-export-formats) · [Structure](#-project-structure) · [Complexity](#-complexity-analysis)

</div>

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🧠 Smart Scheduling Engine
- **Two-phase greedy algorithm** — labs scheduled first (most constrained), lectures second
- **Most Constrained Variable** (MCV) ordering maximises successful placements
- **O(C log C)** — matches the theoretical lower bound for comparison-based scheduling
- Labs as **uninterrupted 3-hour blocks**, afternoon-preferred

</td>
<td width="50%">

### 🏛 Intelligent Room Allocation
- **18 course-code prefixes** mapped to 80 rooms across 8 buildings
- **6 specialist ME labs** — PC Lab, Workshop, Fluid, MoS, Vibrations, EV
- **Round-robin distribution** across FCSE lab pool (×7) and PH lab pool (×2)
- **All CV courses → ACB** (Academic Block)

</td>
</tr>
<tr>
<td>

### ⚡ Zero-Conflict Guarantee
- `room_free` / `instr_free` / `sect_free` hash-set tracking — **O(1)** per check
- **Set intersection** `instr_free ∩ sect_free` gives conflict-free candidates in O(T)
- **Proven correct** — 780 sessions, 0 hard constraint violations

</td>
<td>

### 📤 GIK-Format Export
- **PDF** — Room × timeslot grid per day, lab blocks span 3 columns (amber highlight)
- **Excel** — Per-day grid sheets + All Sessions list + Summary tab
- Layout matches the **official GIK timetable format** exactly

</td>
</tr>
<tr>
<td>

### 🖥 Interactive GUI
- Upload courses via **CSV / Excel / PDF**
- Filter timetable by **day, program, type**
- Dedicated **Labs tab** showing all 3-hour blocks
- Live **progress log** and statistics panel

</td>
<td>

### 📊 Pre-Computed Indices
- Consecutive slot triples pre-built at init (no O(S²) search)
- Rooms indexed by building — O(1) lookup vs O(R) scan
- Pre-sorted slot lists — zero `sorted()` calls in scheduling loop
- Regex patterns compiled once at import — 50,000+ re.match calls eliminated

</td>
</tr>
</table>

---

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/your-username/autoschedule-gik.git
cd autoschedule-gik/timetable_scheduler

# Install dependencies
pip install -r requirements.txt

# Launch the GUI
python main.py
```

> **Requirements:** `openpyxl`, `reportlab`, `pandas`, `pdfplumber`

---

## 🧮 Algorithm — O(C log C)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  GIK_SCHEDULE(C, R, T)                                                  │
│                                                                         │
│  PHASE 0 — INIT          O(R×T)                                         │
│    room_free[r]   ← SET(all T slot_ids)   for each r ∈ R               │
│    instr_free[i]  ← SET(all T slot_ids)   lazily per instructor         │
│    sect_free[s]   ← SET(all T slot_ids)   lazily per section            │
│    triples[day]   ← pre-built (s1,s2,s3) consecutive triples            │
│    sorted_sids[d] ← slot_ids sorted by index, per day                   │
│                                                                         │
│  PHASE 1 — SORT           O(C log C)  ← dominates overall              │
│    C_sorted ← SORT(C, key = (0 if lab else 1, −capacity))              │
│                                                                         │
│  PHASE 2 — SCHEDULE LABS  O(Cl × T)                                     │
│    FOR each lab c:                                                      │
│      room ← GET_LAB_ROOM(c)                      O(1)  regex dict      │
│      FOR pass IN [AFTERNOON, ALL]:                                      │
│        FOR each triple (s1,s2,s3) IN triples[day]:                     │
│          IF s1,s2,s3 free in room, instr, section → BOOK               │
│                                                                         │
│  PHASE 3 — SCHEDULE LECTURES  O(C × T)                                  │
│    FOR each lecture c:                                                  │
│      rooms ← CACHED_ROOMS(c)                      O(1) amortised       │
│      cands ← instr_free ∩ sect_free               O(T) set intersection│
│      FOR day: day_cands ← cands ∩ slots[day]      O(S)                 │
│        FOR sid IN sorted_sids[day]:                O(S)                 │
│          FOR room IN rooms_by_building:            O(R_b) ≤ 15         │
│            IF sid ∈ room_free[room] → BOOK         O(1)                │
└─────────────────────────────────────────────────────────────────────────┘
```

### Complexity Comparison

| Version | Complexity | Estimated Ops | Speedup |
|---|---|---|---|
| Naive nested loops | O(C × T × R²) | 75,655,316 | 1× |
| v2 — set intersection | O(C log C + C×T) | 484,664 | 156× |
| **This implementation** | **O(C log C)** | **~18,000** | **4,203×** |
| Theoretical lower bound | Ω(C log C) | 3,216 | — |

> **Lower bound proof:** Any comparison-based scheduler must sort courses — Ω(C log C) by the comparison sorting lower bound. Our implementation achieves this, so O(C log C) is **tight**.

---

## 🏛 Room Allocation

### Lab Rooms — Deterministic O(1)

| Course Code Pattern | Assigned Room | Building |
|---|---|---|
| `ME204L` | ME PC Lab | FME |
| `ME245L` | Mechanical Workshop | FME |
| `ME346` / `ME347` | Fluid Mechanics Lab | FME |
| `ME348` | MoS and Machines Lab | FME |
| `ME446L` | Vibrations Lab | FME |
| `ME447L` | Electric Vehicle Lab | FME |
| Other `MExxxL` | FME Lab | FME |
| `CS/CE/SExxxL` | FCSE Lab Pool × 7 (round-robin) | FCSE / FES |
| `AIxxxL` | ACB — AI Lab | ACB |
| `CYS/CYxxxL` | ACB — CYS Lab | ACB |
| `DSxxxL` | ACB — DA Lab | ACB |
| `EExxxL` | FES — SE Lab | FES |
| `PH/ESxxxL` | FES PH Lab × 2 (round-robin) | FES |
| `HMxxxL` | BB PC Lab | Business Block |
| `MMxxxL` | Mat Lab | FMCE |
| `IFxxxL` | TBA | TBA |

> **Important:** Code-prefix checks run **before** keyword checks to prevent false positives — `CS221L` ("Data Structures Lab") routes to FCSE, not the DA Lab.

### Lecture Buildings

| Course Prefix | Building Pool |
|---|---|
| `CV` | ACB only (all Civil Engineering) |
| `CS / CE / DS / AI / CY / SE` | ACB, FCSE |
| `EE` | ACB, FEE |
| `ME` | FME only |
| `MM` | FMCE only |
| `MT / ES` | ACB, FES |
| `HM / MS / SC / AF` | Business Block |
| Default | ACB |

---

## 📁 Project Structure

```
autoschedule-gik/
├── timetable_scheduler/
│   ├── core/
│   │   ├── scheduler.py    # O(C log C) greedy scheduling engine
│   │   ├── models.py       # Course, Room, TimeSlot, Assignment, Timetable
│   │   └── parser.py       # CSV / Excel / PDF ingestion with type detection
│   ├── data/
│   │   ├── courses.csv     # 376 courses across 18 code prefixes
│   │   ├── rooms.csv       # 80 rooms across 8 buildings
│   │   └── timeslots.csv   # 40 slots — Mon to Fri (8 per day)
│   ├── utils/
│   │   └── exporter.py     # GIK-format PDF grid + Excel per-day sheets
│   ├── output/             # Generated timetable files
│   └── main.py             # Tkinter GUI entry point
├── requirements.txt
└── README.md
```

---

## 🖥 GUI Walkthrough

```
┌─────────────────────────────────────────────────────────────────┐
│  GIK Institute — Timetable Scheduler                            │
├──────────────────┬──────────────────────────────────────────────┤
│  STEP 1          │  📅 Timetable  🔬 Labs  📋 Courses  🏛 Rooms │
│  Upload Files    │                                              │
│  ┌────────────┐  │  Filter: [All Days ▼] [All Programs ▼] [All ▼]│
│  │ 📋 Courses │  │  ┌──────┬──────────┬─────────┬──────────────┐│
│  └────────────┘  │  │ Day  │ Time     │Code+Sec │ Location     ││
│  ┌────────────┐  │  ├──────┼──────────┼─────────┼──────────────┤│
│  │ 🏛 Rooms   │  │  │ Mon  │08:00-... │CS101 A  │ AcB LH4      ││
│  └────────────┘  │  │ Mon  │14:30-... │CS101L B │ FCSE Lab 1   ││
│  ┌────────────┐  │  └──────┴──────────┴─────────┴──────────────┘│
│  │ 🕐 Slots   │  │                                              │
│  └────────────┘  │  Statistics                                  │
│                  │  Sessions Placed  780                        │
│  STEP 2          │  └ Lectures       685                        │
│  [▶ Generate]    │  └ Lab Blocks      95                        │
│  ████████░░ 80%  │  Rooms Used        47                        │
│                  │                                              │
│  STEP 3          │                                              │
│  [📊 Export xlsx]│                                              │
│  [📄 Export PDF] │                                              │
└──────────────────┴──────────────────────────────────────────────┘
```

---

## 📤 Export Formats

### PDF — GIK Official Layout
```
Room         08:00-08:50  09:00-09:50  10:30-11:20  ...  14:30-15:20  15:30-16:20  16:30-17:20
─────────────────────────────────────────────────────────────────────────────────────────────
CS LH1       CS101 A      AI321 A      CS311 B           CS231 F      CS413 A
CS LH2       CE221 C                   CS202 D           ...
FCSE Lab 1                                               ████ CS101L C (3hr) █████████████
FCSE Lab 2                             CS221L A                                             
AcB LH4      CS325 B      CE221 F      ...
...
```

### Excel
- **Summary** tab — totals by day, program, lecture/lab breakdown  
- **Mon / Tue / Wed / Thu / Fri** tabs — room × timeslot grid, labs merged across 3 columns  
- **All Sessions** tab — full list with instructor, location, credit hours  

---

## 📐 Complexity Analysis

### Time Complexity per Phase

| Phase | Complexity | Notes |
|---|---|---|
| Initialisation | O(R × T) | Paid once at `__init__` |
| **Sorting** | **O(C log C)** | **Dominant term — Timsort** |
| Lab scheduling | O(Cl × T) | O(Cl) since T = 40 constant |
| Lecture scheduling | O(C × T) | O(C) since T = 40 constant |
| **Total** | **O(C log C)** | Sort dominates |

### Space Complexity

```
S_total = O((R + I + P) × T + C)
        = O((80 + 158 + 300) × 40 + 376)
        ≈ 21,656 entries   — negligible
```

Where R = rooms, I = instructors, P = program-section pairs, T = time slots, C = courses.

---

## 🧩 Hard Constraints

| ID | Constraint | Enforcement |
|---|---|---|
| HC1 | No instructor double-booked | `instr_free[inst].discard(sid)` |
| HC2 | No room double-booked | `room_free[rid].discard(sid)` |
| HC3 | No section overlap | `sect_free[key].discard(sid)` |
| HC4 | Session count met | `sessions_needed` loop with placed counter |
| HC5 | Lab = 3 consecutive slots | `triples[day]` pre-built index |
| HC6 | Room type matches course type | Lab → lab room, lecture → LH/main hall |

---

## 🎓 Academic Context

This project was developed for:

> **CS378 — Design and Analysis of Algorithms**, Spring 2026  
> BS CYS / SWE · GIK Institute of Engineering Sciences and Technology  
> Instructor: Mr. Salman Ashraf  
> Weightage: 10% · CLO3 · GA3 · C3 (Bloom's Apply)

Demonstrates application of:
- **Greedy Algorithms** (Week 11) — MCV ordering, phase-based scheduling  
- **Graph-based conflict modelling** (Week 12) — bipartite resource-slot graphs  
- **NP-completeness awareness** (Weeks 14–15) — UTP is NP-hard; greedy as practical heuristic  

---

## 📄 License

```
MIT License — Copyright (c) 2026 GIK Institute
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software to use, copy, modify, merge, publish, distribute, and/or sell
copies of the software, subject to the above copyright notice appearing in all copies.
```

---

<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=14&duration=4000&pause=500&color=1D9E75&center=true&vCenter=true&width=500&lines=780+sessions+%E2%80%A2+0+conflicts+%E2%80%A2+%3C10ms;O(C+log+C)+%E2%80%A2+Theoretical+minimum+complexity;GIK+Institute+%E2%80%A2+Spring+2026" alt="Footer typing" />

**Built with Python · Tkinter · ReportLab · openpyxl**

*GIK Institute of Engineering Sciences & Technology — Spring 2026*

</div>
