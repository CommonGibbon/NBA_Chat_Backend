from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Text, ForeignKey, CheckConstraint
from datetime import datetime
from uuid import UUID, uuid4
from typing import List

# The reason we need this weird base class is because each python model (the classes defined below) need to inherit from the 
# SAME declarativebase instance so that they can communicate with eachother. This allows relationships between tables to work properly.
class Base(DeclarativeBase):
    pass

# represents the chats table:
class Chat(Base):
    __tablename__ = "chats"

    # Primary key, auto-generates UUID
    # syntax is: <class attribute name>: Mapped[<type>] = <tells SQLAlchemy how to map it to the database
    id: Mapped[UUID] = mapped_column(primary_key=True, default = uuid4)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    # Relationship: one chat has many messages. back_populates allows us to automatically append a new message to this list when
    #  new message object when we create a new message object (with a matching chat_id)
    messages: Mapped[List["Message"]] = relationship(back_populates="chat", cascade="all, delete-orphan")

# represents the messages table:
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    chat_id: Mapped[UUID] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    replied_to_id: Mapped[UUID | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    # Relationship: many messages belong to one chat. back_propagates means if we append a new message to a Chat object, 
    # we'll automatically create a new Message object accordinly.
    chat: Mapped["Chat"] = relationship(back_populates="messages")
    user: Mapped["User"] = relationship(back_populates="messages")

    # Constraint matching your scheme - role must be user/assistant/system
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system')", name = "check_role"),
    )

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String, unique=True)
    api_key: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    
    messages: Mapped[List["Message"]] = relationship(back_populates="user", cascade="all, delete-orphan")
