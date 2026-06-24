import React, { useState, useRef, useEffect } from 'react';
import { MessageSquare, Send, Loader2, ChevronDown, ChevronUp } from 'lucide-react';

interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
  action?: string;
}

interface ChatBoxProps {
  sessionId?: string;
  imageId?: string;
  onRenderRequest?: (state: any) => void;
  className?: string;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const ChatBox: React.FC<ChatBoxProps> = ({ sessionId, imageId, onRenderRequest, className = '' }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [chatState, setChatState] = useState<any>({});
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg: ChatMessage = { role: 'user', text: input.trim() };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const formData = new FormData();
      formData.append('message', userMsg.text);
      if (sessionId) formData.append('session_id', sessionId);
      if (imageId) formData.append('image_id', imageId);

      const resp = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        body: formData,
      });
      const data = await resp.json();

      const aiMsg: ChatMessage = {
        role: 'assistant',
        text: data.response || 'Done.',
        action: data.action,
      };
      setMessages(prev => [...prev, aiMsg]);
      setChatState(data.state || {});

      if (data.action === 'render' && onRenderRequest) {
        onRenderRequest(data.state);
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', text: 'Chat unavailable (Ollama offline).' }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className={`chatbox-container ${className}`}>
      <div className="chatbox-header" onClick={() => setExpanded(!expanded)}>
        <MessageSquare size={16} />
        <span className="chatbox-title">Drawing Assistant</span>
        {expanded ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
      </div>

      {expanded && (
        <>
          <div className="chatbox-messages">
            {messages.length === 0 && (
              <div className="chatbox-hint">
                Describe materials, dimensions, or corrections.
                <br />
                e.g. <em>"The base is hammered brass"</em> or <em>"Make top 90cm"</em>
              </div>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`chat-msg chat-msg-${msg.role}`}>
                <div className="chat-msg-text">{msg.text}</div>
                {msg.action === 'render' && (
                  <div className="chat-msg-action">Drawing updated</div>
                )}
              </div>
            ))}
            {loading && (
              <div className="chat-msg chat-msg-assistant">
                <Loader2 size={14} className="spin" />
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="chatbox-input-row">
            <input
              type="text"
              className="chatbox-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Add materials, dimensions, notes..."
              disabled={loading}
            />
            <button
              className="chatbox-send"
              onClick={sendMessage}
              disabled={loading || !input.trim()}
            >
              {loading ? <Loader2 size={14} className="spin" /> : <Send size={14} />}
            </button>
          </div>
        </>
      )}
    </div>
  );
};

export default ChatBox;
