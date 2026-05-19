from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from core.database import Base


class Conversation(Base):
    __tablename__ = "conversation"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("conversationlist.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    user_type= Column("user_type", String(50), nullable=False)
    statement= Column("statement", String(50), nullable=False)
    
    
class ConversationList(Base):
    __tablename__ = "conversationlist"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    conversation_title= Column("conversation_title", String(150), nullable=False)
    is_active = Column("is_Active", Boolean, nullable=False, default=True)
