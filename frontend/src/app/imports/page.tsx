"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type ImportStatus =
  | "UPLOADED" | "VALIDATING" | "VALIDATED" | "PROCESSING"
  | "PROCESSED" | "FAILED_VALIDATION" | "FAILED_PROCESSING" | "ARCHIVED";

interface ImportRecord {
  id: string;
  originalFileName: string;
  storeCode: string | null;
  businessDate: string | null;
  sourceType: string | null;
  uploadedAt: string;
  uploadedBy: string;
  status: ImportStatus;
  recordsExtracted: number;
  errorCount: number;
  fileSize: number;
  checksum: string;
}

const STATUS_STYLES: Record<ImportStatus, string> = {
  UPLOADED: "bg-slate-500/20 text-slate-300 border-slate-500/30",
  VALIDATING: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  VALIDATED: "bg-sky-500/20 text-sky-300 border-sky-500/30",
  PROCESSING: "bg-violet-500/20 text-violet-300 border-violet-500/30",
  PROCESSED: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  FAILED_VALIDATION: "bg-rose-500/20 text-rose-300 border-rose-500/30",
  FAILED_PROCESSING: "bg-rose-500/20 text-rose-300 border-rose-500/30",
  ARCHIVED: "bg-slate-600/20 text-slate-400 border-slate-600/30",
};

const STATUS_DOTS: Record<ImportStatus, string> = {
  UPLOADED: "bg-slate-400",
  VALIDATING: "bg-amber-400 animate-pulse",
  VALIDATED: "bg-sky-400",
  PROCESSING: "bg-violet-400 animate-pulse",
  PROCESSED: "bg-emerald-400",
  FAILED_VALIDATION: "bg-rose-400",
  FAILED_PROCESSING: "bg-rose-400",
  ARCHIVED: "bg-slate-500",
};

function formatBytes(b: number) {
  if (b === 0) return "0 B";
  const k = 1024, i = Math.floor(Math.log(b) / Math.log(k));
  return `${parseFloat((b / Math.pow(k, i)).toFixed(1))} ${["B","KB","MB"][i]}`;
}

export default function ImportsPage() {
  const [imports, setImports] = useState<ImportRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [storeFilter, setStoreFilter] = useState("");

  const fetchImports = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "100" });
      if (statusFilter) params.set("status", statusFilter);
      if (storeFilter) params.set("store_code", storeFilter);
      const res = await fetch(`/api/imports?${params}`);
      if (!res.ok) throw new Error("Failed to fetch imports");
      const data = await res.json();
      setImports(data.imports || []);
      setTotal(data.total || 0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchImports(); }, [statusFilter, storeFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  const statuses: ImportStatus[] = [
    "UPLOADED","VALIDATING","VALIDATED","PROCESSING",
    "PROCESSED","FAILED_VALIDATION","FAILED_PROCESSING","ARCHIVED"
  ];

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      {/* Header */}
      <header className="border-b border-white/5 px-6 py-4 backdrop-blur-md sticky top-0 z-50 bg-slate-950/80">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-slate-400 hover:text-white transition-colors text-sm">
              ← Back
            </Link>
            <div className="h-4 w-px bg-white/10" />
            <span className="font-bold text-white">Import History</span>
            <span className="bg-slate-800 text-slate-400 text-xs px-2 py-0.5 rounded-full border border-white/10">
              {total} records
            </span>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/exports" className="text-xs text-sky-400 hover:text-sky-300 transition-colors bg-sky-500/10 border border-sky-500/20 px-3 py-1.5 rounded-lg">
              ↗ Exports
            </Link>
            <button
              onClick={fetchImports}
              className="text-xs text-slate-400 hover:text-white transition-colors bg-white/5 border border-white/10 px-3 py-1.5 rounded-lg"
            >
              ↻ Refresh
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        {/* Filters */}
        <div className="flex flex-wrap gap-3 items-center">
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="bg-slate-900 border border-white/10 text-sm text-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:border-sky-500/50"
          >
            <option value="">All Statuses</option>
            {statuses.map(s => (
              <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Filter by store code..."
            value={storeFilter}
            onChange={e => setStoreFilter(e.target.value)}
            className="bg-slate-900 border border-white/10 text-sm text-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:border-sky-500/50 w-48"
          />
        </div>

        {/* Table */}
        {loading ? (
          <div className="flex items-center justify-center py-32">
            <div className="flex flex-col items-center gap-3">
              <div className="h-8 w-8 rounded-full border-2 border-sky-500 border-t-transparent animate-spin" />
              <p className="text-slate-500 text-sm">Loading imports…</p>
            </div>
          </div>
        ) : error ? (
          <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-6 text-rose-400 text-sm">{error}</div>
        ) : imports.length === 0 ? (
          <div className="rounded-xl border border-white/5 bg-white/2 p-16 text-center space-y-3">
            <p className="text-4xl">📭</p>
            <p className="text-slate-400">No imports yet. Upload an XML file to get started.</p>
            <Link href="/" className="inline-block text-sky-400 hover:text-sky-300 text-sm transition-colors">
              → Go to Upload
            </Link>
          </div>
        ) : (
          <div className="rounded-2xl border border-white/5 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-white/3 border-b border-white/5">
                  <tr className="text-left text-xs text-slate-500 uppercase tracking-wider">
                    <th className="px-4 py-3">File Name</th>
                    <th className="px-4 py-3">Store</th>
                    <th className="px-4 py-3">Business Date</th>
                    <th className="px-4 py-3">Source</th>
                    <th className="px-4 py-3">Uploaded At</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Records</th>
                    <th className="px-4 py-3 text-right">Errors</th>
                    <th className="px-4 py-3 text-right">Size</th>
                    <th className="px-4 py-3 text-right">Uploaded By</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {imports.map(imp => (
                    <tr key={imp.id} className="hover:bg-white/2 transition-colors group">
                      <td className="px-4 py-3">
                        <span className="text-slate-200 font-mono text-xs max-w-[200px] block truncate" title={imp.originalFileName}>
                          {imp.originalFileName}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sky-400 font-semibold">{imp.storeCode || "—"}</span>
                      </td>
                      <td className="px-4 py-3 text-slate-400">{imp.businessDate || "—"}</td>
                      <td className="px-4 py-3">
                        {imp.sourceType ? (
                          <span className="text-xs bg-slate-800 border border-white/10 px-2 py-0.5 rounded text-slate-300">
                            {imp.sourceType === "POSExport" ? "POS Export" : "Item Maint."}
                          </span>
                        ) : "—"}
                      </td>
                      <td className="px-4 py-3 text-slate-400 text-xs">
                        {new Date(imp.uploadedAt).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border font-medium ${imp.status ? STATUS_STYLES[imp.status] : "bg-slate-500/20 text-slate-300 border-slate-500/30"}`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${imp.status ? STATUS_DOTS[imp.status] : "bg-slate-400"}`} />
                          {imp.status?.replace(/_/g, " ") || "UNKNOWN"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className="text-emerald-400 font-semibold">{imp.recordsExtracted}</span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className={imp.errorCount > 0 ? "text-rose-400 font-semibold" : "text-slate-500"}>
                          {imp.errorCount}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right text-slate-500 text-xs">{formatBytes(imp.fileSize)}</td>
                      <td className="px-4 py-3 text-right text-slate-500 text-xs">{imp.uploadedBy}</td>
                      <td className="px-4 py-3 text-right">
                        <Link
                          href={`/imports/${imp.id}`}
                          className="text-xs text-sky-400 hover:text-white transition-colors opacity-0 group-hover:opacity-100 bg-sky-500/10 border border-sky-500/20 px-2.5 py-1 rounded-lg whitespace-nowrap"
                        >
                          View →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
