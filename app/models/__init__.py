"""ORM models package.

Importing this package ensures every mapped class is registered on
``Base.metadata`` so that ``create_all`` builds the full schema.
"""

from app.models.base import Base
from app.models.global_unavailability import GlobalUnavailability
from app.models.schedule_slot import EntityType, ScheduleSlot
from app.models.student import Student
from app.models.study_group import StudyGroup
from app.models.subject import Subject
from app.models.subject_time_window import SubjectTimeWindow
from app.models.tutor import Tutor
from app.models.tutor_subject import TutorSubject
from app.models.tutor_unavailability import TutorUnavailability

__all__ = [
    "Base",
    "EntityType",
    "GlobalUnavailability",
    "ScheduleSlot",
    "Student",
    "StudyGroup",
    "Subject",
    "SubjectTimeWindow",
    "Tutor",
    "TutorSubject",
    "TutorUnavailability",
]
