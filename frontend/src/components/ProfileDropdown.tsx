"use client";

import { useState, useRef, useEffect } from "react";
import { LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export function ProfileDropdown() {
  const { token, logout } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  
  const [user, setUser] = useState<{ username?: string; role?: string; email?: string } | null>({ username: "User", role: "STORE_MANAGER" });

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    
    // Parse JWT from context token
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        setUser({
          username: payload.name || payload.email || payload.username || "User",
          email: payload.email || "",
          role: payload.role || "STORE_MANAGER"
        });
      } catch (e) {
        setUser({ username: "User", role: "STORE_MANAGER" });
      }
    }

    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [token]);

  if (!user) return null;

  const initial = (user.username || "?").charAt(0).toUpperCase();

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-8 h-8 rounded-full bg-red-950 border border-red-900/50 text-red-500 font-bold flex items-center justify-center hover:bg-red-900/40 transition-colors focus:outline-none"
        title="Profile"
      >
        {initial}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 rounded-xl border border-white/5 bg-[#1a1a1a] shadow-2xl z-50 animate-in fade-in slide-in-from-top-2">
          <div className="px-4 py-3 border-b border-white/5">
            <p className="text-sm font-medium text-white truncate" title={user.email}>{user.email || user.username}</p>
            <p className="text-[10px] uppercase font-bold text-red-500 mt-1 tracking-widest">
              {user.role}
            </p>
          </div>
          <div className="p-1">
            <button
              onClick={() => {
                setIsOpen(false);
                logout();
              }}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:bg-white/5 rounded-lg transition-colors text-left"
            >
              <LogOut className="w-4 h-4" />
              Logout
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
