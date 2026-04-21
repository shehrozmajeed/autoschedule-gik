from dataclasses import dataclass, field
from typing import List


@dataclass
class Course:
    code: str
    section: str
    title: str
    credit_hours: int
    course_type: str       # 'lecture' or 'lab'
    instructor: str
    program: str
    capacity: int = 50
    sessions_needed: int = 0

    def __post_init__(self):
        if self.sessions_needed == 0:
            # Labs are always a single 3-hour block (1 session)
            if self.course_type == 'lab':
                self.sessions_needed = 1
            else:
                self.sessions_needed = min(self.credit_hours, 3)

    @property
    def is_lab(self) -> bool:
        return self.course_type == 'lab'

    @property
    def key(self):
        sec = self.section if self.section else 'X'
        return f"{self.code}_{sec}"

    def __hash__(self):
        return hash(self.key)

    def __eq__(self, other):
        return self.key == other.key

    def __repr__(self):
        return f"Course({self.code} {self.section}, {self.instructor})"


@dataclass
class Room:
    room_id: str
    room_name: str
    building: str
    room_type: str     # 'lecture_hall', 'lab', 'main_hall'
    capacity: int

    def __hash__(self):
        return hash(self.room_id)

    def __eq__(self, other):
        return self.room_id == other.room_id

    def __repr__(self):
        return f"Room({self.room_name}, cap={self.capacity})"


@dataclass
class TimeSlot:
    slot_id: str
    day: str
    start_time: str
    end_time: str
    slot_index: int
    day_type: str      # 'regular' or 'friday'

    def __hash__(self):
        return hash(self.slot_id)

    def __eq__(self, other):
        return self.slot_id == other.slot_id

    def __repr__(self):
        return f"Slot({self.day} {self.start_time}-{self.end_time})"


@dataclass
class Assignment:
    course: Course
    room: Room
    timeslot: TimeSlot
    end_time_override: str = ''   # used for 3-hour lab blocks

    @property
    def display_end_time(self) -> str:
        return self.end_time_override if self.end_time_override else self.timeslot.end_time

    @property
    def location(self) -> str:
        """Human-readable location string for output."""
        return f"{self.room.room_name}"

    def to_dict(self):
        return {
            'Day':           self.timeslot.day,
            'Start Time':    self.timeslot.start_time,
            'End Time':      self.display_end_time,
            'Course Code':   self.course.code,
            'Section':       self.course.section,
            'Course Title':  self.course.title,
            'Type':          self.course.course_type.capitalize(),
            'Credit Hours':  self.course.credit_hours,
            'Instructor':    self.course.instructor,
            'Program':       self.course.program,
            'Room':          self.room.room_name,
            'Building':      self.room.building,
            'Location':      self.location,
            'Room Capacity': self.room.capacity,
            'Students':      self.course.capacity,
        }


@dataclass
class Timetable:
    assignments: List[Assignment] = field(default_factory=list)

    def add(self, assignment: Assignment):
        self.assignments.append(assignment)

    def to_dict_list(self):
        return [a.to_dict() for a in self.assignments]

    def get_by_day(self, day: str):
        return [a for a in self.assignments if a.timeslot.day == day]

    def get_by_program(self, program: str):
        return [a for a in self.assignments if a.course.program == program]

    def get_by_instructor(self, instructor: str):
        return [a for a in self.assignments if a.course.instructor == instructor]

    @property
    def total_scheduled(self):
        return len(self.assignments)
