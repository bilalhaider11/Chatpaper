import "./Chatbot.css";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  deleteFile,

  FileRecord,
  getFiles,
  toFileUrl,
  uploadFile,
  User,
} from "../../services/files_api";
import { conversationList,Conversation } from "../../services/conversation_api";
import { fetchCurrentUser, tokenStore } from '../../api/axios'
import { getConversationList ,getConversation} from "../../services/conversation_api";


function Chatbot() {
  const navigate = useNavigate();
  const [input, setInput] = useState(String)
  const [user, setUser] = useState<User | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [conversationlist, setConversationList] = useState<conversationList[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [chat, setChat] = useState<Conversation[]>([]);

  const loadFiles = async () => {
    const fileList = await getConversationList();
    setConversationList(fileList);
  };

  const loadConversation = async () => {
    const conversations = await getConversation(4);
    setChat(conversations);
  };

  useEffect(() => {
    const bootstrap = async () => {
      
      try {
        await loadConversation();
        await loadFiles();
        
      } finally {
        setLoading(false);
      }
    };

    void bootstrap();
  }, []);

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setMessage("");
    try {
      await uploadFile(selectedFile, description);
      setSelectedFile(null);
      setDescription("");
      setMessage("File uploaded successfully.");
      await loadFiles();
    } catch {
      setMessage("Failed to upload file.");
    } finally {
      setUploading(false);
    }
  };
  const handleSubmit = async () => {

  }



  if (loading) {
    return <div className="home-page">Loading...</div>;
  }


  return (
    <div className="chatbot-page">
      <aside className="chatbot-sidebar">
        <h2>Chats</h2>
        <button> New Chat</button>
        <div className="file-list">
          <h3>Files</h3>
          {conversationlist.length === 0 ? (
            <p className="upload-card-subtitle">No files uploaded yet.</p>
          ) : (
            conversationlist.map((file) => (
              <div key={file.id} className="file-row">
                <a href={toFileUrl(file.conversation_title)} target="_blank" rel="noreferrer">
                  {file.id} {file.conversation_title}
                </a>
              </div>
            ))
          )}
        </div>
      </aside >
      <main className="chatbot-main">
        <header className="chatbot-header">
          <h1>Assistant</h1>
          <span>UI only (API integration pending)</span>
        </header>
        <section className="chatbot-messages">
          <div className="chat-msg user">Show me a summary of the latest uploaded file.</div>

          <div className="chat-msg bot">This is placeholder UI. Hook chat API in the next step.</div>
          <div className="file-list">
          {chat.length === 0 ? (
            <p className="upload-card-subtitle">No files uploaded yet.</p>
          ) : (
            chat.map((file) => (
              <div key={file.id} className="file-row">
                
                  {file.user_type} {file.statement}
                
              </div>
            ))
          )}
        </div>
        </section>
        <footer className="chatbot-input">
          <input placeholder="Type your message..."  value={input}/>
          <button onClick={handleSubmit}>Send</button>
        </footer>
      </main>
    </div >
  );
}

export default Chatbot;
