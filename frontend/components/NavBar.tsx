import React from "react";
import { Globe, Upload, BookOpen, BarChart3, GitBranch, Ruler, Database, TrendingUp, Zap, Cpu, History, FileImage } from "lucide-react";

export type Tab = "upload" | "crawl" | "crawl-to-svg" | "templates" | "calibration" | "analytics" | "resources" | "improvements" | "engineering" | "workflow" | "history";

interface NavBarProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "upload", label: "Upload & Digitize", icon: <Upload size={14} /> },
  { id: "crawl", label: "Crawl Product", icon: <Globe size={14} /> },
  { id: "crawl-to-svg", label: "Crawl to SVG", icon: <FileImage size={14} /> },
  { id: "templates", label: "Templates (18)", icon: <BookOpen size={14} /> },
  { id: "calibration", label: "Calibration", icon: <BarChart3 size={14} /> },
  { id: "analytics", label: "Analytics", icon: <TrendingUp size={14} /> },
  { id: "resources", label: "Resources", icon: <Database size={14} /> },
  { id: "improvements", label: "Improvements", icon: <Zap size={14} /> },
  { id: "engineering", label: "Engineering", icon: <Cpu size={14} /> },
  { id: "workflow", label: "How It Works", icon: <GitBranch size={14} /> },
];

export default function NavBar({ activeTab, onTabChange }: NavBarProps) {
  return (
    <nav className="w-full bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-5xl mx-auto px-4">
        <div className="flex items-center h-14 gap-1 overflow-x-auto">
          <div className="flex items-center gap-2 mr-4 shrink-0">
            <Ruler size={18} className="text-indigo-600" />
            <span className="text-sm font-bold text-gray-800 whitespace-nowrap">CAD Digitizer</span>
          </div>
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg whitespace-nowrap transition-colors ${
                activeTab === tab.id
                  ? "bg-indigo-100 text-indigo-700"
                  : "text-gray-500 hover:text-gray-700 hover:bg-gray-100"
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
          <div className="ml-auto flex items-center gap-2">
            <a
              href="/api/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-gray-400 hover:text-gray-600 underline"
            >
              API Docs
            </a>
            <a
              href="https://github.com/jpgyap-sudo/cad-scaler-digitizer"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              GitHub
            </a>
          </div>
        </div>
      </div>
    </nav>
  );
}
