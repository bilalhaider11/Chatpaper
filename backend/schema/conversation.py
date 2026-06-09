from typing import Literal

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
    conversation_title: str
    is_active: bool
    conversation_type: str
    file_id: int | None = None
    model_config = ConfigDict(from_attributes=True)


class ConversationCreateRequest(BaseModel):
    conversation_title: str = "Global conversation"
    # per_file conversations are created automatically on file upload — not via this endpoint
    conversation_type: Literal["global"] = "global"


class ConversationListRequest(BaseModel):
    conversation_title: str
    is_active: bool


#################################### Conversation ################################################

class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    chat_id: int | None = None
    statement: str
    user_type: str


class ChatWsSendPayload(BaseModel):
    action: str = "send"
    statement: str
