from pathlib import Path
from uuid import uuid4
import shutil

from fastapi import Body,APIRouter, Depends, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from schema.websocket import manager
from core.dependencies import get_db
from models.conversation import Conversation,ConversationList
from schema.conversation import ConversationListResponse, ConversationResponse, ConversationListBase
from core.auth import get_current_user
from services import conversation as conversation_service
router = APIRouter(prefix="/conversation", tags=["conversation"])

    
@router.post("/inconversationlist", response_model=ConversationListResponse)
async def conversation_list(
    
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return conversation_service.create_conversation_list(current_user,db)
    
    

@router.patch("/conversation-title/{conversation_id}")
async def update_conversation_title(
    conversation_id: int,
    title: str = Body(..., embed=True),
    current_user=Depends(get_current_user),
    db: Session=Depends(get_db)   
):
    return conversation_service.update_conversation_title(title ,conversation_id, db)

@router.get("/get_conversation_list",response_model=list[ConversationListResponse])
async def get_conersation_list(
    current_user=Depends(get_current_user),
    db: Session=Depends(get_db)):
 
    
    return db.query(ConversationList).where(ConversationList.user_id == current_user.id , ConversationList.is_active == True).all()
    

@router.post("/conversation/{chat_id}",response_model=ConversationResponse)
async def conversation(
    chat_id:int,
    data: ConversationResponse,
    current_user=Depends(get_current_user),
    db: Session=Depends(get_db)
):
    
    return conversation_service.add_conversation(data, chat_id, db)


@router.get("/get-conversation/{chat_list_id}",response_model=list[ConversationResponse])
async def get_conversation(
    chat_list_id:int,
    current_user=Depends(get_current_user),
    db: Session=Depends(get_db)
):
    return conversation_service.get_conversations(chat_list_id, db)
    
@router.delete("/delete_list/{list_id}")
async def delete_conversation_list(
    list_id:int,
    current_user=Depends(get_current_user),
    db:Session=Depends(get_db)
):
    return conversation_service.delete_conversation_list(list_id, db)


##################################################################################################################

@router.websocket("/chat/{tunnel_id}/{user_id}")
async def websocket_chat_endpoint(websocket: WebSocket, tunnel_id: str, user_id: str):
    await manager.connect(websocket, tunnel_id)
    try:
        while True:
            data = await websocket.receive_text()
            
            # Streaming simulation: breaking the text into chunks for slow UI updates
            chunk_size = 5
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]
                
                # Format: "User_Id: chunk" or a strict JSON payload
                formatted_payload = f"{user_id}: {chunk}"
                
                # Stream the message to the other users in the tunnel
                await manager.broadcast(formatted_payload, tunnel_id, sender=websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, tunnel_id)