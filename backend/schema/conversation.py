from datetime import datetime

from pydantic import BaseModel, ConfigDict

############################# Conversation list ###################################################

class ConversationListBase(BaseModel):
    conversation_title: str | None = None


class ConversationListUpdate(BaseModel):
    id: int
    conversation_title: str | None = None
    is_active: bool | None = None


class ConversationListResponse(ConversationListBase):
    id: int
    file_id: int
    conversation_title: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class ConversationListCreate(BaseModel):
    file_id: int


class ConversationListRequest(BaseModel):
    conversation_title: str
    is_active: bool
    file_id: int


#################################### Conversation ################################################

class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    chat_id: int | None = None
    temp_id: str | None = None
    created_at: datetime | None = None
    statement: str
    user_type: str
    streaming: bool = False


class ConversationPageResponse(BaseModel):
    messages: list[ConversationResponse]
    next_cursor_id: int | None = None


class ConversationCreate(BaseModel):
    statement: str


class ChatWsSendPayload(BaseModel):
    action: str = "send"
    statement: str
    user_type: str
    