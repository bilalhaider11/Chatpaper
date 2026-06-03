from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

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


class ConversationTitleUpdate(BaseModel):
    conversation_title: str | None = None
    title: str | None = None

    model_config = ConfigDict(populate_by_name=True)

    def resolved_title(self) -> str:
        value = (self.conversation_title or self.title or "").strip()
        if not value:
            raise ValueError("conversation_title is required")
        return value

    @model_validator(mode="after")
    def validate_title_present(self):
        if not (self.conversation_title or self.title or "").strip():
            raise ValueError("conversation_title is required")
        return self


class ConversationListCreate(BaseModel):
    file_id: int


class ConversationCreateRequest(BaseModel):
    conversation_title: str = "New conversation"
    # per_file conversations are created automatically on file upload — not via this endpoint
    conversation_type: Literal["global"] = "global"


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
