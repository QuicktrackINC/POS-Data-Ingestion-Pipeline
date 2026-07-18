"use client";

import React, { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { login as loginApi } from "@/lib/api";
import { User, Lock, ArrowRight, Loader2, Fuel } from "lucide-react";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await loginApi(username, password);
      await login(data.access_token);
    } catch (err: any) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#050505]">
      {/* Cinematic Mesh Gradient Background */}
      <div className="absolute inset-0 z-0">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-red-900/20 blur-[120px] animate-pulse" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-blue-900/10 blur-[120px] animate-pulse" style={{ animationDelay: '2s' }} />
        <div className="absolute top-[20%] right-[10%] w-[30%] h-[30%] rounded-full bg-red-600/5 blur-[100px]" />
      </div>

      {/* Grid Pattern Overlay */}
      <div className="absolute inset-0 z-0 opacity-20" 
           style={{ backgroundImage: 'radial-gradient(circle, #333 1px, transparent 1px)', backgroundSize: '40px 40px' }} />

      <div className="relative z-10 w-full max-w-md px-6">
        <div className="mb-10 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-red-500 to-red-700 p-0.5 mb-6 shadow-2xl shadow-red-500/20">
             <div className="w-full h-full bg-[#0a0a0a] rounded-[14px] flex items-center justify-center">
                <Fuel className="w-8 h-8 text-red-500" />
             </div>
          </div>
          <h1 className="text-4xl font-bold tracking-tight text-white mb-2 font-outfit">
            POS
          </h1>
          <p className="text-gray-400 font-medium">Data Ingestion Pipeline</p>
        </div>

        <div className="backdrop-blur-2xl bg-white/[0.03] border border-white/10 rounded-3xl p-8 shadow-2xl">
          <form className="space-y-6" onSubmit={handleSubmit}>
            {error && (
              <div className="p-4 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl animate-in fade-in slide-in-from-top-2">
                {error}
              </div>
            )}
            
            <div className="space-y-4">
              <div className="group relative">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <User className="h-5 w-5 text-gray-500 group-focus-within:text-red-500 transition-colors" />
                </div>
                <input
                  type="text"
                  required
                  autoComplete="username"
                  className="block w-full pl-11 pr-4 py-4 bg-white/5 border border-white/10 rounded-xl text-white placeholder:text-gray-600 focus:ring-2 focus:ring-red-500/50 focus:border-red-500/50 focus:bg-white/[0.07] outline-none transition-all"
                  placeholder="Username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>

              <div className="group relative">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-gray-500 group-focus-within:text-red-500 transition-colors" />
                </div>
                <input
                  type="password"
                  required
                  autoComplete="current-password"
                  className="block w-full pl-11 pr-4 py-4 bg-white/5 border border-white/10 rounded-xl text-white placeholder:text-gray-600 focus:ring-2 focus:ring-red-500/50 focus:border-red-500/50 focus:bg-white/[0.07] outline-none transition-all"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="relative w-full group overflow-hidden bg-red-600 hover:bg-red-500 text-white font-bold py-4 rounded-xl shadow-lg shadow-red-600/20 transition-all disabled:opacity-50 active:scale-[0.98]"
            >
              <div className="relative z-10 flex items-center justify-center gap-2">
                {loading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Processing...</span>
                  </>
                ) : (
                  <>
                    <span>Enter Dashboard</span>
                    <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                  </>
                )}
              </div>
            </button>
          </form>
          
          <div className="relative mt-8">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-white/10"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-transparent text-gray-500 backdrop-blur-xl">Or continue with</span>
            </div>
          </div>

          <div className="mt-6">
            <a
              href={`${process.env.NEXT_PUBLIC_HUB_URL || "https://quicktrackhub.vercel.app"}/api/tools/pos-pipeline/launch`}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl transition-colors text-white font-medium"
            >
              <div className="flex h-6 w-6 items-center justify-center rounded bg-orange-500 text-xs font-black">
                Q
              </div>
              Login via QuickTrack Hub
            </a>
          </div>
          
          <div className="mt-8 pt-6 border-t border-white/5 text-center">
            <p className="text-xs text-gray-600 uppercase tracking-widest font-semibold">
              Proprietary System • Quicktrack Inc.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
