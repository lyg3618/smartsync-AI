from sqlalchemy import Column, Integer, String, Text, BigInteger, Date, Boolean, Enum, DateTime, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class MeetingStatus(str, enum.Enum):
    uploading = "uploading"
    processing = "processing"
    ready_for_review = "ready_for_review"
    dispatched = "dispatched"

class ActionStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"

class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    date = Column(Date)
    duration_sec = Column(Integer, default=0)
    file_path = Column(String(512))
    transcript_path = Column(String(512))
    user_id = Column(String(50), nullable=True)
    status = Column(Enum(MeetingStatus), default=MeetingStatus.uploading)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    summaries = relationship("Summary", back_populates="meeting", uselist=False)
    action_items = relationship("ActionItem", back_populates="meeting")
    transcripts = relationship("Transcript", back_populates="meeting", order_by="Transcript.start_ms")

class Summary(Base):
    __tablename__ = "summaries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), unique=True)
    text = Column(Text)
    decisions = Column(Text)  # JSON array string
    meeting = relationship("Meeting", back_populates="summaries")

class Contact(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False)
    calendar_addr = Column(String(255))
    user_id = Column(String(50), nullable=True)
    username = Column(String(50), unique=True, nullable=True)
    hashed_password = Column(String(255), nullable=True)
    role = Column(String(20), default="user")

class ActionItem(Base):
    __tablename__ = "action_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    owner_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    content = Column(Text, nullable=False)
    due_date = Column(Date)
    status = Column(Enum(ActionStatus), default=ActionStatus.pending)
    is_viewed = Column(Boolean, nullable=False, default=False)
    viewed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    progress_note = Column(Text, nullable=True)
    updated_after_dispatch = Column(Boolean, nullable=False, default=False)
    last_dispatched_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    meeting = relationship("Meeting", back_populates="action_items")
    owner = relationship("Contact")

class Transcript(Base):
    __tablename__ = "transcripts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    start_ms = Column(BigInteger, default=0)
    end_ms = Column(BigInteger, default=0)
    text = Column(Text)
    meeting = relationship("Meeting", back_populates="transcripts")

class DispatchLog(Base):
    __tablename__ = "dispatch_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    payload = Column(JSON)
    success = Column(Boolean, default=False)
    message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
