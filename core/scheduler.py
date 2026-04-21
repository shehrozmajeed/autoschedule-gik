"""
GIK Timetable Scheduler — Maximum Optimisation
================================================
Complexity
----------
  Theoretical lower bound : Omega(C log C)
  This implementation     : O(C log C)

  Proof of lower bound
  --------------------
  Any correct scheduler must:
    1. Read every course                → Omega(C)
    2. Sort by constraint degree (MCV) → Omega(C log C)  [comparison-based]
    3. Write every assignment           → Omega(C)
  Omega(C log C) is therefore tight.

  All per-course work after sorting is O(1) amortised:
    - Room lookup  : pre-indexed dict      O(1)
    - Slot search  : set intersection      O(T)  with T=40 a fixed constant
    - Conflict chk : hash-set membership   O(1)
  So the scheduling loop is O(C × T) = O(C) since T is constant.
  Sort dominates → O(C log C) overall.

Weekly Load Distribution Policy
--------------------------------
  Monday – Thursday  : PRIMARY scheduling days (heavy load).
                       Lectures and labs are filled here first.
  Friday             : LIGHT day. At most _FRIDAY_MAX_PER_SECT lecture
                       sessions are placed per section on Friday.
                       Labs are NEVER placed on Friday unless no
                       Mon–Thu triple exists.
  This mirrors the GIK Institute academic calendar where Friday is
  reserved for Jumu'ah prayers and lighter academic activities.

Lab Room Mapping (deterministic, O(1))
--------------------------------------
  ME204L               → ME PC Lab          (FME)
  ME245L               → Mechanical Workshop (FME)
  ME346 / ME347 /
  ME447 (fluid kw)     → Fluid Mechanics Lab (FME)
  ME348 (mos/machines) → MoS and Machines Lab (FME)
  ME446L (vibration kw)→ Vibrations Lab      (FME)
  ME447L (vehicle kw)  → Electric Vehicle Lab (FME)
  Other MExxxL         → FME Lab             (FME)

  CS/CE/SE labs        → rotate across FCSE SE Lab pool (only FCSE_SE_LAB)
  ES/PH labs           → rotate across FES PH Lab pool
  AI labs              → ACB - AI Lab
  CYS/CY labs          → ACB - CYS Lab
  DS labs              → ACB - DA Lab
  EE labs              → FES - SE Lab
  HM labs              → BB Main  (HM courses/labs are exclusively in BB;
                          BB has no dedicated PC lab, so BB Main is used)
  IF labs              → TBA
  MM labs              → Mat Lab (FMCE)

Lecture Building Routing
------------------------
  CS/CE/DS/AI/CY/SE/EE → ACB  (primary, with FCSE as secondary)
  CV                   → ACB  (all CV courses)
  ME                   → FME
  MM                   → FMCE
  HM/MS/SC/AF          → Business Block  ← ALL HM lectures AND labs in BB only
  MT/ES                → ACB + FES
  Default              → ACB
"""

import re
import random
from typing import List, Dict, Set, Tuple, Optional, Callable
from core.models import Course, Room, TimeSlot, Assignment, Timetable

# ── Constants ─────────────────────────────────────────────────────────────────
_AFTERNOON = 6
_TBA_SET   = {'TBA', 'TBD', ''}

# ── Weekly load distribution ──────────────────────────────────────────────────
# Maximum lecture sessions per section that may be placed on Friday.
# Set to 1 so Friday gets at most one lecture per section (light day).
_FRIDAY_MAX_PER_SECT = 1

# Canonical Mon–Thu ordering; Friday is always appended last in day priority.
_WEEKDAYS       = ['Monday', 'Tuesday', 'Wednesday', 'Thursday']
_FRIDAY         = 'Friday'

# ── Compiled regex patterns — built ONCE at import ────────────────────────────
_RE = {k: re.compile(v) for k, v in {
    # Lab patterns
    'ME_PC'    : r'^ME2?04L',
    'ME_WS'    : r'^ME2?45L',
    'ME_FLUID' : r'^ME3?4[67]L?',
    'ME_MOS'   : r'^ME3?48L?',
    'ME_VIB'   : r'^ME4?46L',
    'ME_EV'    : r'^ME4?47L',
    'ME'       : r'^ME\d+L',
    'PH'       : r'^PH\d+L',
    'AI'       : r'^AI\d+L',
    'CYS'      : r'^CYS?\d+L',
    'DS'       : r'^DS\d+L',
    'CS'       : r'^(CS|CE|SE)\d+L',
    'EE'       : r'^EE\d+L',
    'MM'       : r'^MM\d+L',
    'ES'       : r'^ES\d+L',
    'HM'       : r'^HM\d+L',
    # Lecture building patterns
    'L_BB'     : r'^(HM|MS|SC|AF)\d',
    'L_FES'    : r'^(MT|ES)\d',
    'L_FCSE'   : r'^(CS|CE|DS|AI|CY|SE)\d',
    'L_FEE'    : r'^EE\d',
    'L_FME'    : r'^ME\d',
    'L_FMCE'   : r'^MM\d',
    'L_CV'     : r'^CV\d',
}.items()}

# Title keywords for ME lab special cases
_ME_FLUID_KW  = ('fluid', 'fluids')
_ME_MOS_KW    = ('mos', 'mechanics of solid', 'machines')
_ME_VIB_KW    = ('vibration', 'vibrations')
_ME_EV_KW     = ('electric vehicle', 'ev technology')
_ME_WS_KW     = ('workshop',)

# Generic FME keyword list (any ME-related title → FME Lab fallback)
_FME_KW = ('fluid', 'heat', 'vibration', 'workshop', 'mos', 'vehicle',
            'mechanical', 'mechanics of solid', 'machines')

# DA keywords — specific phrases only (avoid "data structures" false hits)
_DA_KW  = ('big data', 'data science', 'data engineering', 'data analytics',
            'data mining', 'database', 'data visualization')

# ── Lab room pools (round-robin to distribute load) ───────────────────────────
# FCSE now has only ONE lab (SE Lab) — PC_LAB and FCSE_LAB1-4 were removed.
FCSE_LAB_POOL = [
    'FCSE_SE_LAB',
]
PH_LAB_POOL = ['PH_LAB', 'PH_LAB2']

_fcse_idx = 0
_ph_idx   = 0


def _next_fcse() -> str:
    global _fcse_idx
    r = FCSE_LAB_POOL[_fcse_idx % len(FCSE_LAB_POOL)]
    _fcse_idx += 1
    return r


def _next_ph() -> str:
    global _ph_idx
    r = PH_LAB_POOL[_ph_idx % len(PH_LAB_POOL)]
    _ph_idx += 1
    return r


# ── O(1) lab room assignment ──────────────────────────────────────────────────

def get_lab_room_id(course: Course) -> str:
    """
    Deterministic lab-room assignment in O(1).
    Code-prefix checks run BEFORE keyword checks to prevent false positives
    (e.g. CS221L = 'Data Structures Lab' must NOT go to DA Lab).

    ME labs use a two-level check:
      Level 1 — specific course code  (ME204L, ME245L, ME346, ME348, ME446L, ME447L)
      Level 2 — title keyword         (fluid, mos, vibration, vehicle, workshop)
      Level 3 — generic ME fallback   (FME Lab)
    """
    code  = course.code.upper().strip()
    title = course.title.lower().strip()

    # ── IF → TBA ──────────────────────────────────────────────────────────────
    if code.startswith('IF'):
        return 'TBA_ROOM'

    # ── ME labs — specific room per course/keyword ────────────────────────────
    if _RE['ME_PC'].match(code):                      return 'ME_PC_LAB'
    if _RE['ME_WS'].match(code):                      return 'ME_WORKSHOP'
    if _RE['ME_FLUID'].match(code):                   return 'ME_FLUID_LAB'
    if _RE['ME_MOS'].match(code):                     return 'ME_MOS_LAB'
    if _RE['ME_VIB'].match(code):                     return 'ME_VIB_LAB'
    if _RE['ME_EV'].match(code):                      return 'ME_EV_LAB'
    if _RE['ME'].match(code):
        # keyword fallback for unlisted ME lab codes
        for kw in _ME_FLUID_KW:
            if kw in title:                           return 'ME_FLUID_LAB'
        for kw in _ME_MOS_KW:
            if kw in title:                           return 'ME_MOS_LAB'
        for kw in _ME_VIB_KW:
            if kw in title:                           return 'ME_VIB_LAB'
        for kw in _ME_EV_KW:
            if kw in title:                           return 'ME_EV_LAB'
        for kw in _ME_WS_KW:
            if kw in title:                           return 'ME_WORKSHOP'
        return 'FME_LAB'

    # ── PH labs ───────────────────────────────────────────────────────────────
    if _RE['PH'].match(code):                         return _next_ph()

    # ── AI labs ───────────────────────────────────────────────────────────────
    if _RE['AI'].match(code):                         return 'ACB_AI_LAB'

    # ── CYS / CY labs ─────────────────────────────────────────────────────────
    if _RE['CYS'].match(code):                        return 'ACB_CYS_LAB'

    # ── DS labs ───────────────────────────────────────────────────────────────
    if _RE['DS'].match(code):                         return 'ACB_DA_LAB'

    # ── CS / CE / SE → rotate FCSE pool ──────────────────────────────────────
    # MUST precede DA keyword check: CS221L = "Data Structures Lab"
    if _RE['CS'].match(code):                         return _next_fcse()

    # ── EE labs ───────────────────────────────────────────────────────────────
    # MUST precede DA keyword check: EE222L = "Data Structures Lab"
    if _RE['EE'].match(code):                         return 'FES_SE_LAB'

    # ── MM → Mat Lab ──────────────────────────────────────────────────────────
    if _RE['MM'].match(code):                         return 'MAT_LAB'

    # ── ES labs → PH lab pool ─────────────────────────────────────────────────
    if _RE['ES'].match(code):                         return _next_ph()

    # ── HM → BB Main (HM labs are exclusively in Business Block;
    #    BB_PC_LAB no longer exists in rooms.csv so BB_MAIN is used) ───────────
    if _RE['HM'].match(code):                         return 'BB_MAIN'

    # ── Keyword fallbacks (unrecognised prefixes only) ─────────────────────────
    for kw in _FME_KW:
        if kw in title:                               return 'FME_LAB'
    for kw in _DA_KW:
        if kw in title:                               return 'ACB_DA_LAB'

    return 'TBA_ROOM'


# ── O(1) lecture building pool ────────────────────────────────────────────────

def get_lecture_building_pool(code: str) -> List[str]:
    """
    Returns allowed buildings for a lecture course.
    All CV courses → ACB (Academic Block).
    """
    if _RE['L_CV'].match(code):    return ['ACB']
    if _RE['L_BB'].match(code):    return ['Business Block']
    if _RE['L_FES'].match(code):   return ['ACB', 'FES']
    if _RE['L_FCSE'].match(code):  return ['ACB', 'FCSE']
    if _RE['L_FEE'].match(code):   return ['ACB', 'FEE']
    if _RE['L_FME'].match(code):   return ['FME']
    if _RE['L_FMCE'].match(code):  return ['FMCE']
    return ['ACB']


# ── Scheduler ─────────────────────────────────────────────────────────────────

class Scheduler:
    """
    Two-phase Greedy Scheduler — O(C log C) time complexity.

    Phase 1 — Labs    : fixed room O(1), search pre-built triples O(T)
    Phase 2 — Lectures: room via pre-index O(1), candidates via set ∩ O(T),
                        inner room scan O(R_building) ≤ 15

    Weekly Load Distribution
    ------------------------
    Monday–Thursday are treated as PRIMARY days.  The scheduler fills
    these days before touching Friday, which is kept as a LIGHT day:

      • Lectures : day priority always puts Friday LAST.
                   A per-section Friday counter (_fri_sect_count) caps
                   the number of lecture sessions placed on Friday at
                   _FRIDAY_MAX_PER_SECT (default = 1).

      • Labs     : consecutive 3-hour blocks are searched on Mon–Thu
                   first (_try_weekday).  Friday is used only as a
                   last resort if no Mon–Thu triple is available
                   (_try_friday_fallback).

    Pre-computed at __init__ (paid once):
      _rooms_by_bld[bld]          O(R)   — rooms per building, sorted by capacity
      _triples[day]               O(T)   — consecutive slot triples for lab search
      _sorted_sids_by_day[day]    O(T)   — slot_ids sorted by index, no re-sort needed
      _room_free[rid]             O(R×T) — free-slot sets, updated on every booking
      _instr_free / _sect_free           — lazily initialised, O(T) each
    """

    def __init__(
        self,
        courses    : List[Course],
        rooms      : List[Room],
        timeslots  : List[TimeSlot],
        progress_cb: Optional[Callable[[str], None]] = None,
    ):
        self.courses   = courses
        self.rooms     = rooms
        self.timeslots = timeslots
        self.cb        = progress_cb

        self.assignments : List[Assignment] = []
        self.unscheduled : List[Tuple[Course, str]] = []

        # O(R) — room id dict
        self._room_by_id: Dict[str, Room] = {r.room_id: r for r in rooms}

        # O(R) — rooms by building, sorted by capacity once
        self._rooms_by_bld: Dict[str, List[Room]] = {}
        for r in rooms:
            if r.room_type in ('lecture_hall', 'main_hall'):
                self._rooms_by_bld.setdefault(r.building, []).append(r)
        for bld in self._rooms_by_bld:
            self._rooms_by_bld[bld].sort(key=lambda r: r.capacity)

        # O(T) — slot dicts
        self._slot_by_id: Dict[str, TimeSlot] = {s.slot_id: s for s in timeslots}
        all_sids: Set[str] = set(self._slot_by_id)

        # O(T) — slots per day, sorted
        _by_day: Dict[str, List[TimeSlot]] = {}
        for s in timeslots:
            _by_day.setdefault(s.day, []).append(s)
        for d in _by_day:
            _by_day[d].sort(key=lambda x: x.slot_index)

        # O(T) — slot_id sets and sorted lists per day
        self._sids_by_day: Dict[str, Set[str]] = {
            d: {s.slot_id for s in sl} for d, sl in _by_day.items()
        }
        self._sorted_sids_by_day: Dict[str, List[str]] = {
            d: [s.slot_id for s in sl] for d, sl in _by_day.items()
        }

        # O(D×S) — pre-built consecutive triples for lab scheduling
        self._triples: Dict[str, List[Tuple]] = {}
        for day, sl in _by_day.items():
            triples = []
            for i in range(len(sl) - 2):
                s1, s2, s3 = sl[i], sl[i+1], sl[i+2]
                if (s2.slot_index == s1.slot_index + 1 and
                        s3.slot_index == s2.slot_index + 1):
                    triples.append((
                        s1, s2, s3,
                        s1.slot_index >= _AFTERNOON,
                        f"{s1.slot_id},{s2.slot_id},{s3.slot_id}",
                        s3.end_time,
                    ))
            self._triples[day] = triples

        # O(R×T) — free-slot sets for rooms
        self._room_free: Dict[str, Set[str]] = {
            r.room_id: set(all_sids) for r in rooms
        }

        # Lazy free-slot sets for instructors and sections
        self._instr_free : Dict[str, Set[str]] = {}
        self._sect_free  : Dict[str, Set[str]] = {}
        self._all_sids   = all_sids

        # ── Weekly-load distribution setup ────────────────────────────────────
        # Build Mon–Thu day list (shuffled for variety) then append Friday last.
        available_days = set(_by_day.keys())

        weekdays_present = [d for d in _WEEKDAYS if d in available_days]
        random.shuffle(weekdays_present)              # variety within Mon–Thu

        # _day_order is the canonical ordering used throughout: Mon–Thu first,
        # Friday always last regardless of shuffle.
        self._day_order: List[str] = weekdays_present
        if _FRIDAY in available_days:
            self._day_order.append(_FRIDAY)

        # Separate sets for fast day-type checks
        self._weekday_set: Set[str] = set(weekdays_present)
        self._friday_in_pool: bool  = _FRIDAY in available_days

        # Per-section Friday lecture counter.  Keyed by _prog_key(course).
        # Incremented whenever a lecture is placed on Friday; capped at
        # _FRIDAY_MAX_PER_SECT before any further Friday placement is allowed.
        self._fri_sect_count: Dict[str, int] = {}

        # Pre-built slot-id sets for quick day-type filtering
        self._friday_sids: Set[str] = self._sids_by_day.get(_FRIDAY, set())
        self._weekday_sids: Set[str] = set()
        for d in self._weekday_set:
            self._weekday_sids |= self._sids_by_day.get(d, set())

        # Per-course room cache — (prefix, cap_bucket) → List[Room]
        self._room_cache: Dict[Tuple, List[Room]] = {}

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _log(self, msg: str):
        if self.cb:
            self.cb(msg)

    @staticmethod
    def _prog_key(c: Course) -> str:
        return f"{c.program}_{c.section}"

    def _instr_set(self, inst: str) -> Set[str]:
        if inst not in self._instr_free:
            self._instr_free[inst] = set(self._all_sids)
        return self._instr_free[inst]

    def _sect_set(self, course: Course) -> Set[str]:
        key = self._prog_key(course)
        if key not in self._sect_free:
            self._sect_free[key] = set(self._all_sids)
        return self._sect_free[key]

    def _book(self, a: Assignment):
        """O(k) where k = slots booked (1 lecture, 3 lab)."""
        rid  = a.room.room_id
        inst = a.course.instructor.upper()
        for sid in a.timeslot.slot_id.split(','):
            sid = sid.strip()
            self._room_free[rid].discard(sid)
            if inst not in _TBA_SET:
                self._instr_set(inst).discard(sid)
            self._sect_set(a.course).discard(sid)
        self.assignments.append(a)

    def _course_rooms(self, course: Course) -> List[Room]:
        """
        O(1) amortised — cached by (2-letter prefix, capacity bucket).
        First miss: O(R_building) ≤ 15.
        """
        code  = course.code.upper()
        key   = (code[:2], (course.capacity // 10) * 10)
        if key in self._room_cache:
            return self._room_cache[key]

        pools  = get_lecture_building_pool(code)
        chosen = random.choice(pools)

        def _get(bld, strict=True):
            return [r for r in self._rooms_by_bld.get(bld, [])
                    if not strict or r.capacity >= course.capacity]

        rooms = _get(chosen) or _get(chosen, False)
        if not rooms:
            for bld in pools:
                rooms = _get(bld) or _get(bld, False)
                if rooms:
                    break
        if not rooms:
            rooms = [r for r in self.rooms
                     if r.room_type in ('lecture_hall', 'main_hall')]

        self._room_cache[key] = rooms
        return rooms

    # ── Lab scheduling — O(T) per lab ────────────────────────────────────────

    def _schedule_lab(self, course: Course) -> bool:
        """
        Search for a consecutive 3-hour block.

        Priority:
          1. Afternoon slots on Mon–Thu  (pm_only=True, weekday_only=True)
          2. Any slot on Mon–Thu         (pm_only=False, weekday_only=True)
          3. Afternoon slots on Friday   (pm_only=True, weekday_only=False) — fallback
          4. Any slot on Friday          (pm_only=False, weekday_only=False) — last resort
        """
        rid  = get_lab_room_id(course)
        room = self._room_by_id.get(rid)
        if room is None:
            # BB_PC_LAB and PC_LAB are removed from rooms.csv;
            # fallback chain uses only rooms that still exist.
            for fb in ('FES_SE_LAB', 'FCSE_SE_LAB', 'FME_LAB', 'TBA_ROOM'):
                room = self._room_by_id.get(fb)
                if room:
                    rid = fb
                    break
        if room is None:
            self.unscheduled.append((course, 'No lab room resolved'))
            return False

        rf     = self._room_free[rid]
        inst   = course.instructor.upper()
        i_free = self._instr_set(inst) if inst not in _TBA_SET else None
        s_free = self._sect_set(course)

        def _try(pm_only: bool, weekday_only: bool):
            # Build the day list: weekdays-only or all days (weekdays + Friday last)
            if weekday_only:
                days = [d for d in self._day_order if d in self._weekday_set]
            else:
                days = list(self._day_order)   # Mon–Thu already before Friday

            for day in days:
                for s1, s2, s3, is_pm, cids, et in self._triples.get(day, []):
                    if pm_only and not is_pm:
                        continue
                    ids = (s1.slot_id, s2.slot_id, s3.slot_id)
                    if not (ids[0] in rf and ids[1] in rf and ids[2] in rf):
                        continue
                    if i_free is not None and not (
                            ids[0] in i_free and ids[1] in i_free
                            and ids[2] in i_free):
                        continue
                    if not (ids[0] in s_free and ids[1] in s_free
                            and ids[2] in s_free):
                        continue
                    return s1, cids, et
            return None

        # 4-pass search: prefer weekday PM → weekday any → Friday PM → Friday any
        result = (
            _try(True,  True)  or   # Mon–Thu afternoon
            _try(False, True)  or   # Mon–Thu any time
            _try(True,  False) or   # Friday afternoon (fallback)
            _try(False, False)      # Friday any time  (last resort)
        )

        if result is None:
            self.unscheduled.append((course, f'No 3-hr block in {room.room_name}'))
            return False

        s1, cids, et = result
        vslot = TimeSlot(slot_id=cids, day=s1.day,
                         start_time=s1.start_time, end_time=et,
                         slot_index=s1.slot_index, day_type=s1.day_type)
        self._book(Assignment(course=course, room=room,
                              timeslot=vslot, end_time_override=et))
        self._log(f"  LAB {course.code} {course.section} → "
                  f"{s1.day} {s1.start_time}–{et} → {room.room_name}")
        return True

    # ── Lecture scheduling — O(T) per session ────────────────────────────────

    def _schedule_lecture(self, course: Course) -> bool:
        """
        Candidate slots = instr_free ∩ sect_free   O(T) set intersection
        Per day: filter candidates by day            O(S)  using pre-sorted list
        Per slot: check rooms in building            O(R_building) ≤ 15
        Room-free check                              O(1)  hash set

        Friday load control
        -------------------
        _day_order already places Friday last, so Mon–Thu slots are
        exhausted before any Friday slot is considered.  Additionally,
        once a section has reached _FRIDAY_MAX_PER_SECT sessions on
        Friday, all Friday slots are excluded from the candidate set for
        that section for the remainder of scheduling.
        """
        inst   = course.instructor.upper()
        i_free = self._instr_set(inst) if inst not in _TBA_SET else None
        s_free = self._sect_set(course)
        rooms  = self._course_rooms(course)

        sect_key = self._prog_key(course)
        used_days: Set[str] = set()
        placed = 0

        for _ in range(course.sessions_needed):
            candidates: Set[str] = (
                (i_free & s_free) if i_free is not None else set(s_free)
            )

            # ── Friday cap: remove Friday slots if quota is exhausted ─────────
            fri_used = self._fri_sect_count.get(sect_key, 0)
            if fri_used >= _FRIDAY_MAX_PER_SECT:
                # Exclude all Friday slots from consideration this session
                candidates -= self._friday_sids

            if not candidates:
                break

            # Day priority: unused days first (variety), Friday always last
            weekday_unused   = [d for d in self._day_order
                                 if d in self._weekday_set and d not in used_days]
            weekday_used     = [d for d in self._day_order
                                 if d in self._weekday_set and d in used_days]
            friday_days      = [_FRIDAY] if (
                                    self._friday_in_pool and
                                    fri_used < _FRIDAY_MAX_PER_SECT
                               ) else []

            day_priority = weekday_unused + weekday_used + friday_days

            found = False
            for day in day_priority:
                day_cands = candidates & self._sids_by_day.get(day, set())
                if not day_cands:
                    continue
                for sid in self._sorted_sids_by_day[day]:
                    if sid not in day_cands:
                        continue
                    for room in rooms:
                        if sid in self._room_free[room.room_id]:
                            self._book(Assignment(
                                course=course, room=room,
                                timeslot=self._slot_by_id[sid]))
                            used_days.add(day)
                            placed += 1
                            # Update Friday counter if this slot is on Friday
                            if day == _FRIDAY:
                                self._fri_sect_count[sect_key] = (
                                    self._fri_sect_count.get(sect_key, 0) + 1
                                )
                            found = True
                            break
                    if found:
                        break
                if found:
                    break

            if not found:
                break

        if placed == 0:
            self.unscheduled.append((course, 'No free slot/room found'))
            return False
        if placed < course.sessions_needed:
            self.unscheduled.append((course,
                f'Only {placed}/{course.sessions_needed} sessions placed'))
        return placed > 0

    # ── Main entry — O(C log C) ───────────────────────────────────────────────

    def run(self) -> Timetable:
        total = len(self.courses)
        self._log(f"Scheduler: {total} courses | "
                  f"Mode: Mon–Thu heavy, Friday light "
                  f"(max {_FRIDAY_MAX_PER_SECT} lecture/section on Friday)")

        # O(C log C) — sort dominates; all scheduling is O(C) after this
        ordered = sorted(self.courses,
                         key=lambda c: (0 if c.is_lab else 1, -c.capacity))

        for idx, course in enumerate(ordered):
            if idx % 20 == 0:
                self._log(f"  {idx+1}/{total} …")
            if course.is_lab:
                self._schedule_lab(course)
            else:
                self._schedule_lecture(course)

        # ── Load distribution summary ─────────────────────────────────────────
        day_counts: Dict[str, int] = {}
        for a in self.assignments:
            day = a.timeslot.day.split(',')[0]   # lab triples: take first day
            day_counts[day] = day_counts.get(day, 0) + 1

        self._log("Load distribution by day:")
        total_placed = sum(day_counts.values())
        for day in self._day_order:
            n   = day_counts.get(day, 0)
            pct = (n / total_placed * 100) if total_placed else 0
            bar = '█' * int(pct / 4)
            tag = ' ← light day' if day == _FRIDAY else ''
            self._log(f"  {day:<12} {n:>4} sessions  ({pct:5.1f}%)  {bar}{tag}")

        self._log(
            f"Done — {len(self.assignments)} scheduled, "
            f"{len(self.unscheduled)} unscheduled."
        )
        tt = Timetable()
        for a in self.assignments:
            tt.add(a)
        return tt

    def get_unscheduled_report(self) -> List[str]:
        return [f"{c.code} {c.section} ({c.program}) — {r}"
                for c, r in self.unscheduled]