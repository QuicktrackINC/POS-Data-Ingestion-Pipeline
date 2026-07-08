"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import XmlUploader from "@/components/XmlUploader";
import ItemCatalog from "@/components/ItemCatalog";
import SalesDashboard from "@/components/SalesDashboard";
import { ProfileDropdown } from "@/components/ProfileDropdown";

interface DashboardMetrics {
  totalImports: number;
  successfulImports: number;
  failedImports: number;
  lastSuccessfulImport: string | null;
  lastSuccessfulFile: string | null;
  unknownProducts: number;
}

function OperationalDashboard() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/dashboard")
      .then(r => r.json())
      .then(setMetrics)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      {[...Array(6)].map((_, i) => (
        <div key={i} className="h-20 rounded-xl bg-white/3 border border-white/5 animate-pulse" />
      ))}
    </div>
  );

  if (!metrics) return null;

  const successRate = metrics.totalImports > 0
    ? Math.round((metrics.successfulImports / metrics.totalImports) * 100)
    : 0;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {[
          { label: "Total Imports", value: metrics.totalImports, icon: "📂", color: "text-white", link: null },
          { label: "Successful", value: metrics.successfulImports, icon: "✅", color: "text-emerald-400", link: null },
          { label: "Failed", value: metrics.failedImports, icon: "❌", color: metrics.failedImports > 0 ? "text-rose-400" : "text-slate-500", link: null },
          { label: "Success Rate", value: `${successRate}%`, icon: "📈", color: successRate >= 90 ? "text-emerald-400" : successRate >= 70 ? "text-amber-400" : "text-rose-400", link: null },
          { label: "Unknown Products", value: metrics.unknownProducts, icon: "❓", color: metrics.unknownProducts > 0 ? "text-amber-400" : "text-slate-500", link: "/products" },
          { label: "Last Success", value: metrics.lastSuccessfulImport ? new Date(metrics.lastSuccessfulImport).toLocaleDateString() : "—", icon: "🕐", color: "text-sky-400", link: null },
        ].map(({ label, value, icon, color, link }) => (
          link ? (
            <Link href={link} key={label} className="bg-white/3 border border-white/5 hover:border-sky-500/50 hover:bg-white/5 transition-colors rounded-xl p-4 space-y-1 block group">
              <div className="flex items-center justify-between">
                <p className="text-xs text-slate-500">{icon} {label}</p>
                <span className="text-sky-400 text-xs opacity-0 group-hover:opacity-100 transition-opacity">Map →</span>
              </div>
              <p className={`text-xl font-bold ${color}`}>{value}</p>
            </Link>
          ) : (
            <div key={label} className="bg-white/3 border border-white/5 rounded-xl p-4 space-y-1">
              <p className="text-xs text-slate-500">{icon} {label}</p>
              <p className={`text-xl font-bold ${color}`}>{value}</p>
            </div>
          )
        ))}
      </div>
      {metrics.lastSuccessfulFile && (
        <p className="text-xs text-slate-600 text-center">
          Last: <span className="text-slate-500 font-mono">{metrics.lastSuccessfulFile}</span>
        </p>
      )}
    </div>
  );
}

export default function HomePage() {
  const [activeTab, setActiveTab] = useState<"sales" | "catalog">("sales");

  return (
    <main className="min-h-screen flex flex-col bg-slate-950">
      {/* Nav */}
      <header className="border-b border-white/5 px-6 py-4 backdrop-blur-md sticky top-0 z-50 bg-slate-950/50">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl" aria-hidden>🗂️</span>
            <span className="font-bold text-white tracking-tight">
              QuickTrack <span className="text-sky-400">Integration Core</span>
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/imports" className="hidden sm:flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white transition-colors bg-white/5 border border-white/10 hover:border-white/20 px-3 py-1.5 rounded-lg">
              📋 Import History
            </Link>
            <Link href="/exports" className="hidden sm:flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white transition-colors bg-white/5 border border-white/10 hover:border-white/20 px-3 py-1.5 rounded-lg">
              ↓ Exports
            </Link>
            <nav className="hidden sm:flex items-center gap-1 p-1 bg-white/5 rounded-xl border border-white/10">
              <button onClick={() => setActiveTab("sales")} className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${activeTab === "sales" ? "bg-sky-500 text-white shadow-lg" : "text-slate-400 hover:text-white"}`}>
                Sales
              </button>
              <button onClick={() => setActiveTab("catalog")} className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${activeTab === "catalog" ? "bg-sky-500 text-white shadow-lg" : "text-slate-400 hover:text-white"}`}>
                Catalog
              </button>
            </nav>
            <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 text-xs font-medium text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Online
            </span>
            <div className="ml-2 pl-4 border-l border-white/10">
              <ProfileDropdown />
            </div>
          </div>
        </div>
      </header>

      {/* Hero + Uploader */}
      <section className="px-6 pt-12 pb-6">
        <div className="max-w-xl w-full mx-auto space-y-8">
          <div className="text-center space-y-2">
            <h1 className="text-4xl sm:text-5xl font-bold tracking-tight gradient-text">
              POS Data Ingestion
            </h1>
            <p className="text-slate-400 text-sm leading-relaxed">
              Upload XML exports from your POS system. Files are validated, normalized, stored, and ready for export.
            </p>
          </div>
          <div className="glass p-6 sm:p-8 shadow-2xl shadow-black/40">
            <div className="mb-4">
              <h2 className="text-xs font-semibold text-slate-300 uppercase tracking-widest">Upload XML</h2>
              <p className="text-xs text-slate-500 mt-1">
                Supports <code className="text-sky-400">POSExport</code> and <code className="text-sky-400">ItemMaintenance</code> formats.
              </p>
            </div>
            <XmlUploader />
          </div>
        </div>
      </section>

      {/* Operational Dashboard */}
      <section className="px-6 pb-4">
        <div className="max-w-xl mx-auto space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-widest">Ingestion Health</h2>
            <Link href="/imports" className="text-xs text-sky-400 hover:text-sky-300 transition-colors">
              View all →
            </Link>
          </div>
          <OperationalDashboard />
        </div>
      </section>

      {/* Quick links on mobile */}
      <section className="px-6 pb-4 sm:hidden">
        <div className="flex gap-2">
          <Link href="/imports" className="flex-1 text-center text-xs font-semibold text-slate-400 bg-white/5 border border-white/10 px-3 py-2 rounded-lg">
            📋 Import History
          </Link>
          <Link href="/exports" className="flex-1 text-center text-xs font-semibold text-slate-400 bg-white/5 border border-white/10 px-3 py-2 rounded-lg">
            ↓ Exports
          </Link>
        </div>
      </section>

      {/* Data tabs */}
      <section className="px-6 pb-20">
        <div className="sm:hidden flex justify-center mb-6">
          <nav className="flex items-center gap-1 p-1 bg-white/5 rounded-xl border border-white/10">
            <button onClick={() => setActiveTab("sales")} className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition-all ${activeTab === "sales" ? "bg-sky-500 text-white" : "text-slate-400 hover:text-white"}`}>Sales</button>
            <button onClick={() => setActiveTab("catalog")} className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition-all ${activeTab === "catalog" ? "bg-sky-500 text-white" : "text-slate-400 hover:text-white"}`}>Catalog</button>
          </nav>
        </div>
        {activeTab === "sales" ? <SalesDashboard /> : <ItemCatalog />}
      </section>

      <footer className="mt-auto border-t border-white/5 px-6 py-8 text-center text-[10px] text-slate-600 uppercase tracking-[0.2em]">
        Quicktrack Inc · Integration Core · v1.0.0
      </footer>
    </main>
  );
}
