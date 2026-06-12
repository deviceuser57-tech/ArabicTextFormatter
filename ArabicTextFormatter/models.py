from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    projects = relationship("Project", back_populates="workspace", cascade="all, delete")

class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=generate_uuid)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    workspace = relationship("Workspace", back_populates="projects")
    
    settings = relationship("ProjectSetting", back_populates="project", uselist=False, cascade="all, delete")
    documents = relationship("Document", back_populates="project", cascade="all, delete")
    knowledge_items = relationship("KnowledgeItem", back_populates="project", cascade="all, delete")
    memories = relationship("ProjectMemory", back_populates="project", cascade="all, delete")

# Unified project settings & rules
class ProjectSetting(Base):
    __tablename__ = "project_settings"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    knowledge_web_ratio = Column(Float, nullable=False, default=0.7)
    document_type = Column(String, nullable=False, default="General")
    export_style_json = Column(Text, nullable=True)
    rules_json = Column(Text, nullable=False, default='{"language": "Arabic", "rtl": true, "style": "Formal", "citation_required": false, "numbering": "Legal", "heading_style": "Standard"}')

    project = relationship("Project", back_populates="settings")

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    current_version_id = Column(String, nullable=True)
    metadata_json = Column("metadata", Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete")

class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    document_model = Column(Text, nullable=False)
    version_note = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    document = relationship("Document", back_populates="versions")

class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(Text, nullable=True)
    references_text = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    project = relationship("Project", back_populates="knowledge_items")

class ProjectMemory(Base):
    __tablename__ = "project_memory"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    project = relationship("Project", back_populates="memories")
