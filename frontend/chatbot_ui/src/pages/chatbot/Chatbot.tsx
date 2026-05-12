import "./Chatbot.css";

function Chatbot() {
  return (
    <div className="chatbot-page">
      <aside className="chatbot-sidebar">
        <h2>Chats</h2>
        <button> New Chat</button>
        <ul>
          <li>Document Summary</li>
          <li>Contract Review</li>
          <li>Knowledge Base Q&A</li>
        </ul>
      </aside>
      <main className="chatbot-main">
        <header className="chatbot-header">
          <h1>Assistant</h1>
          <span>UI only (API integration pending)</span>
        </header>
        <section className="chatbot-messages">
          <div className="chat-msg bot">Hello. Upload files from Home, then ask me questions here.</div>
          <div className="chat-msg user">Show me a summary of the latest uploaded file.</div>
          <div className="chat-msg bot">This is placeholder UI. Hook chat API in the next step.</div>
        </section>
        <footer className="chatbot-input">
          <input placeholder="Type your message..."/>
          <button>Send</button>
        </footer>
      </main>
    </div>
  );
}

export default Chatbot;
