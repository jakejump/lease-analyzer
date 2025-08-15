import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import declarative_base, relationship
import enum


Base = declarative_base()


class Role(str, enum.Enum):
    owner = "owner"
    editor = "editor"
    viewer = "viewer"


def _id() -> str:
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_id)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=True)
    role = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True, default=_id)
    owner_id = Column(String, ForeignKey("users.id"), nullable=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User")


class ProjectMember(Base):
    __tablename__ = "project_members"
    id = Column(String, primary_key=True, default=_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    role = Column(Enum(Role), default=Role.viewer)

    project = relationship("Project")
    user = relationship("User")


class LeaseVersionStatus(str, enum.Enum):
    uploaded = "uploaded"
    processed = "processed"
    failed = "failed"


class LeaseVersion(Base):
    __tablename__ = "lease_versions"
    id = Column(String, primary_key=True, default=_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    label = Column(String, nullable=True)
    content_hash = Column(String, nullable=True)
    file_url = Column(String, nullable=True)
    pages_url = Column(String, nullable=True)
    chunks_url = Column(String, nullable=True)
    faiss_dir = Column(String, nullable=True)
    ocr_dpi = Column(String, nullable=True)
    status = Column(Enum(LeaseVersionStatus), default=LeaseVersionStatus.uploaded)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project")


