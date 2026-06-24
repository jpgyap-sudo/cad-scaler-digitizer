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

      // Use /py-api/ proxy pattern (same as cadEngine.ts)
      const base = import.meta.env.VITE_CAD_ENGINE_URL || '';
      const apiUrl = base.startsWith('http')
        ? `${base}/api/chat`
        : `${window.location.origin}/py-api/chat`;

      const resp = await fetch(apiUrl, {
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
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: 'Chat unavailable. Make sure OPENAI_API_KEY is set on the server.'
      }]);
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
    <div className={className}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center space-x-2 px-3 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm font-medium"
      >
        <MessageSquare size={16} />
        <span>Drawing Assistant</span>
        {expanded ? <ChevronDown size={14} className="ml-auto" /> : <ChevronUp size={14} className="ml-auto" />}
      </button>

      {expanded && (
        <div className="mt-2 border border-slate-200 rounded-lg overflow-hidden bg-white">
          <div className="h-48 overflow-y-auto p-3 space-y-2 bg-slate-50" style={{ minHeight: '120px', maxHeight: '220px' }}>
            {messages.length === 0 && (
              <div className="text-xs text-slate-400 text-center py-4 leading-relaxed">
                <p className="font-medium text-slate-500 mb-1">Describe your item</p>
                <p>e.g. <em className="text-indigo-500">"The base is hammered brass"</em></p>
                <p>e.g. <em className="text-indigo-500">"Make the top 90cm diameter"</em></p>
                <p>e.g. <em className="text-indigo-500">"This is a round pedestal table"</em></p>
              </div>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`text-xs ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
                <div className={`inline-block px-3 py-1.5 rounded-lg max-w-[85%] ${
                  msg.role === 'user'
                    ? 'bg-indigo-600 text-white rounded-br-sm'
                    : 'bg-white border border-slate-200 text-slate-700 rounded-bl-sm'
                }`}>
                  {msg.text}
                  {msg.action === 'render' && (
                    <div className="text-[10px] mt-1 text-indigo-300">drawing updated</div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="text-left">
                <div className="inline-block px-3 py-1.5 rounded-lg bg-white border border-slate-200">
                  <Loader2 size={14} className="animate-spin text-indigo-400" />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="flex items-center border-t border-slate-200 p-2 gap-2 bg-white">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Description, materials, dimensions..."
              disabled={loading}
              className="flex-1 px-3 py-1.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-indigo-400 disabled:opacity-50"
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              className="p-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-40 transition-colors"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatBox;
