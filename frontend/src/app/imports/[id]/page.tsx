"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { use } from "react";

interface ImportDetail {
  import: {
    id: string;
    originalFileName: string;
    storeCode: string | null;
    businessDate: string | null;
    sourceType: string | null;
    uploadedAt: string;
    uploadedBy: string;
    status: string;
    recordsExtracted: number;
    errorCount: number;
    fileSize: number;
    checksum: string;
    parserVersion: string;
  };
  timeline: Array<{ status: string; note: string | null; createdAt: string }>;
  errors: Array<{ errorType: string; message: string; field: string | null; createdAt: string }>;
  extracted: {
    dailySales: Record<string, unknown>[];
    lineItems: Record<string, unknown>[];
    departments: Record<string, unknown>[];
    fuel: Record<string, unknown>[];
  };
  rawXml: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  UPLOADED: "text-slate-300 bg-slate-500/20 border-slate-500/30",
  VALIDATING: "text-amber-300 bg-amber-500/20 border-amber-500/30",
  VALIDATED: "text-sky-300 bg-sky-500/20 border-sky-500/30",
  PROCESSING: "text-violet-300 bg-violet-500/20 border-violet-500/30",
  PROCESSED: "text-emerald-300 bg-emerald-500/20 border-emerald-500/30",
  FAILED_VALIDATION: "text-rose-300 bg-rose-500/20 border-rose-500/30",
  FAILED_PROCESSING: "text-rose-300 bg-rose-500/20 border-rose-500/30",
  ARCHIVED: "text-slate-400 bg-slate-600/20 border-slate-600/30",
};

const STATUS_ORDER = [
  "UPLOADED","VALIDATING","VALIDATED","PROCESSING","PROCESSED",
  "FAILED_VALIDATION","FAILED_PROCESSING","ARCHIVED"
];

function formatBytes(b: number) {
  if (!b) return "0 B";
  const k = 1024, i = Math.floor(Math.log(b) / Math.log(k));
  return `${parseFloat((b / Math.pow(k, i)).toFixed(1))} ${["B","KB","MB"][i]}`;
}

export default function ImportDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [data, setData] = useState<ImportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showRaw, setShowRaw] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);
  const [reprocessMsg, setReprocessMsg] = useState("");
  const [activeTab, setActiveTab] = useState<"summary" | "items" | "dept" | "fuel" | "errors">("summary");

  const fetchDetail = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/imports/${id}`);
      if (!res.ok) throw new Error("Import not found");
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDetail(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleReprocess = async () => {
    if (!confirm("Reprocess this import? Previous extracted data will be replaced.")) return;
    setReprocessing(true);
    setReprocessMsg("");
    try {
      const res = await fetch(`/api/imports/${id}/reprocess`, { method: "POST" });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || "Reprocess failed");
      setReprocessMsg(`✅ Reprocessed — ${body.records_extracted} records extracted`);
      await fetchDetail();
    } catch (e) {
      setReprocessMsg(`❌ ${e instanceof Error ? e.message : "Failed"}`);
    } finally {
      setReprocessing(false);
    }
  };

  const downloadRawXml = () => {
    if (!data?.rawXml) return;
    const blob = new Blob([data.rawXml], { type: "text/xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = data.import.originalFileName;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="h-8 w-8 rounded-full border-2 border-sky-500 border-t-transparent animate-spin" />
    </div>
  );

  if (error) return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6">
      <div className="text-rose-400 text-center space-y-2">
        <p className="text-2xl">⚠️</p>
        <p>{error}</p>
        <Link href="/imports" className="text-sky-400 hover:text-sky-300 text-sm">← Back to imports</Link>
      </div>
    </div>
  );

  if (!data || !data.import) return null;
  const imp = data.import;
  const isFailed = imp.status?.startsWith("FAILED");

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/5 px-6 py-4 sticky top-0 z-50 bg-slate-950/80 backdrop-blur-md">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/imports" className="text-slate-400 hover:text-white transition-colors text-sm">← Imports</Link>
            <div className="h-4 w-px bg-white/10" />
            <span className="font-mono text-xs text-slate-400 truncate max-w-sm">{imp.originalFileName}</span>
            <span className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full border font-medium ${imp.status ? STATUS_COLORS[imp.status] : "text-slate-300 bg-slate-800 border-white/10"}`}>
              {imp.status?.replace(/_/g, " ") || "UNKNOWN"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {data.rawXml && (
              <button onClick={downloadRawXml} className="text-xs text-slate-400 hover:text-white bg-white/5 border border-white/10 px-3 py-1.5 rounded-lg transition-colors">
                ↓ Download XML
              </button>
            )}
            <button
              onClick={handleReprocess}
              disabled={reprocessing}
              className="text-xs text-violet-300 bg-violet-500/10 border border-violet-500/20 hover:bg-violet-500/20 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
            >
              {reprocessing ? "Reprocessing…" : "↺ Reprocess"}
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        {reprocessMsg && (
          <div className={`rounded-xl border p-3 text-sm ${reprocessMsg.startsWith("✅") ? "border-emerald-500/20 bg-emerald-500/5 text-emerald-400" : "border-rose-500/20 bg-rose-500/5 text-rose-400"}`}>
            {reprocessMsg}
          </div>
        )}

        {/* File Info Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Store", value: imp.storeCode || "—", accent: true },
            { label: "Business Date", value: imp.businessDate || "—" },
            { label: "Records", value: (imp.recordsExtracted ?? 0).toString(), green: true },
            { label: "Errors", value: (imp.errorCount ?? 0).toString(), red: (imp.errorCount ?? 0) > 0 },
          ].map(({ label, value, accent, green, red }) => (
            <div key={label} className="bg-white/3 border border-white/5 rounded-xl p-4 space-y-1">
              <p className="text-xs text-slate-500 uppercase tracking-wider">{label}</p>
              <p className={`text-xl font-bold ${accent ? "text-sky-400" : green ? "text-emerald-400" : red ? "text-rose-400" : "text-white"}`}>
                {value}
              </p>
            </div>
          ))}
        </div>

        {/* Meta info */}
        <div className="bg-white/2 border border-white/5 rounded-xl p-4 grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs">
          {[
            ["Import ID", imp.id],
            ["Source Type", imp.sourceType || "Unknown"],
            ["Uploaded By", imp.uploadedBy],
            ["Uploaded At", new Date(imp.uploadedAt).toLocaleString()],
            ["File Size", formatBytes(imp.fileSize)],
            ["Parser Version", imp.parserVersion],
          ].map(([k, v]) => (
            <div key={k}>
              <p className="text-slate-500">{k}</p>
              <p className="text-slate-300 font-mono truncate" title={v}>{v}</p>
            </div>
          ))}
          <div className="col-span-2 sm:col-span-3">
            <p className="text-slate-500">Checksum (SHA-256)</p>
            <p className="text-slate-400 font-mono text-[10px] break-all">{imp.checksum}</p>
          </div>
        </div>

        {/* Timeline */}
        <div className="space-y-2">
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-widest">Status Timeline</h2>
          <div className="relative pl-6">
            <div className="absolute left-2 top-0 bottom-0 w-px bg-white/10" />
            {data.timeline?.map((ev, i) => (
              <div key={i} className="relative mb-3 last:mb-0">
                <div className={`absolute -left-4 top-1.5 h-2 w-2 rounded-full ${ev.status && STATUS_COLORS[ev.status]?.includes("emerald") ? "bg-emerald-400" : ev.status && STATUS_COLORS[ev.status]?.includes("rose") ? "bg-rose-400" : ev.status && STATUS_COLORS[ev.status]?.includes("violet") ? "bg-violet-400" : "bg-slate-500"}`} />
                <div className="bg-white/2 border border-white/5 rounded-lg px-3 py-2">
                  <div className="flex items-center justify-between">
                    <span className={`text-xs font-semibold ${ev.status && STATUS_COLORS[ev.status]?.includes("emerald") ? "text-emerald-400" : ev.status && STATUS_COLORS[ev.status]?.includes("rose") ? "text-rose-400" : ev.status && STATUS_COLORS[ev.status]?.includes("violet") ? "text-violet-400" : "text-slate-300"}`}>
                      {ev.status?.replace(/_/g, " ") || "UNKNOWN"}
                    </span>
                    <span className="text-[10px] text-slate-500">{new Date(ev.createdAt).toLocaleString()}</span>
                  </div>
                  {ev.note && <p className="text-xs text-slate-400 mt-0.5">{ev.note}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Tabs for extracted data */}
        <div className="space-y-4">
          <nav className="flex items-center gap-1 p-1 bg-white/5 rounded-xl border border-white/10 w-fit">
            {(["summary", "items", "dept", "fuel", "errors"] as const).map(t => (
              <button
                key={t}
                onClick={() => setActiveTab(t)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all capitalize ${activeTab === t ? "bg-sky-500 text-white shadow-lg" : "text-slate-400 hover:text-white"}`}
              >
                {t === "summary" ? "Daily Sales" : t === "dept" ? "Departments" : t === "items" ? "Line Items" : t === "fuel" ? "Fuel" : `Errors ${data.errors?.length > 0 ? `(${data.errors.length})` : ""}`}
              </button>
            ))}
          </nav>

          {activeTab === "summary" && (
            <div className="space-y-2">
              {!data.extracted?.dailySales?.length ? (
                <p className="text-slate-500 text-sm py-6 text-center">No daily sales summary extracted.</p>
              ) : data.extracted.dailySales.map((d, i) => (
                <div key={i} className="bg-white/2 border border-white/5 rounded-xl p-4 grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
                  <div><p className="text-slate-500">Gross Sales</p><p className="text-emerald-400 font-bold text-base">${Number(d.grossSales).toFixed(2)}</p></div>
                  <div><p className="text-slate-500">Net Sales</p><p className="text-white font-semibold">${Number(d.netSales).toFixed(2)}</p></div>
                  <div><p className="text-slate-500">Tax</p><p className="text-slate-300">${Number(d.taxAmount).toFixed(2)}</p></div>
                  <div><p className="text-slate-500">Transactions</p><p className="text-sky-400 font-bold">{String(d.transactionCount)}</p></div>
                  <div><p className="text-slate-500">Cash</p><p className="text-slate-300">${Number(d.cashAmount).toFixed(2)}</p></div>
                  <div><p className="text-slate-500">Credit</p><p className="text-slate-300">${Number(d.creditAmount).toFixed(2)}</p></div>
                  <div><p className="text-slate-500">Fuel Sales</p><p className="text-amber-400">${Number(d.fuelSales).toFixed(2)}</p></div>
                  <div><p className="text-slate-500">Avg Ticket</p><p className="text-slate-300">${Number(d.averageTicket).toFixed(2)}</p></div>
                </div>
              ))}
            </div>
          )}

          {activeTab === "items" && (
            <div className="rounded-xl border border-white/5 overflow-hidden">
              {!data.extracted?.lineItems?.length ? (
                <p className="text-slate-500 text-sm py-6 text-center">No line items extracted.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-white/3 border-b border-white/5">
                      <tr className="text-slate-500 uppercase tracking-wider">
                        {["Item","Code","Dept","Qty","Unit Price","Sales Amt","Tax"].map(h => (
                          <th key={h} className="px-3 py-2 text-left">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {data.extracted.lineItems.slice(0, 100).map((li, i) => (
                        <tr key={i} className="hover:bg-white/2 transition-colors">
                          <td className="px-3 py-2 text-slate-300 max-w-[160px] truncate">{String(li.itemName)}</td>
                          <td className="px-3 py-2 font-mono text-slate-500">{String(li.itemCode || "—")}</td>
                          <td className="px-3 py-2 text-slate-400">{String(li.department || "—")}</td>
                          <td className="px-3 py-2 text-slate-300">{String(li.quantity)}</td>
                          <td className="px-3 py-2 text-slate-300">${Number(li.unitPrice).toFixed(2)}</td>
                          <td className="px-3 py-2 text-emerald-400">${Number(li.salesAmount).toFixed(2)}</td>
                          <td className="px-3 py-2 text-slate-400">${Number(li.taxAmount).toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {data.extracted.lineItems.length > 100 && (
                    <p className="text-xs text-slate-500 text-center py-3">Showing 100 of {data.extracted.lineItems.length} items</p>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === "dept" && (
            <div className="rounded-xl border border-white/5 overflow-hidden">
              {!data.extracted?.departments?.length ? (
                <p className="text-slate-500 text-sm py-6 text-center">No department data extracted.</p>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-white/3 border-b border-white/5">
                    <tr className="text-slate-500 uppercase tracking-wider">
                      {["Department","Qty Sold","Gross","Net","Tax","Discounts"].map(h => (
                        <th key={h} className="px-3 py-2 text-left">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {data.extracted.departments.map((d, i) => (
                      <tr key={i} className="hover:bg-white/2">
                        <td className="px-3 py-2 text-slate-300">{String(d.department)}</td>
                        <td className="px-3 py-2 text-slate-400">{String(d.quantitySold)}</td>
                        <td className="px-3 py-2 text-emerald-400">${Number(d.grossAmount).toFixed(2)}</td>
                        <td className="px-3 py-2 text-slate-300">${Number(d.netAmount).toFixed(2)}</td>
                        <td className="px-3 py-2 text-slate-400">${Number(d.taxAmount).toFixed(2)}</td>
                        <td className="px-3 py-2 text-amber-400">${Number(d.discountAmount).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {activeTab === "fuel" && (
            <div className="rounded-xl border border-white/5 overflow-hidden">
              {!data.extracted?.fuel?.length ? (
                <p className="text-slate-500 text-sm py-6 text-center">No fuel data in this import.</p>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-white/3 border-b border-white/5">
                    <tr className="text-slate-500 uppercase tracking-wider">
                      {["Grade","Gallons","Sales","$/Gal","Pump"].map(h => (
                        <th key={h} className="px-3 py-2 text-left">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {data.extracted.fuel.map((f, i) => (
                      <tr key={i} className="hover:bg-white/2">
                        <td className="px-3 py-2 text-amber-400">{String(f.fuelGrade)}</td>
                        <td className="px-3 py-2 text-slate-300">{Number(f.gallons).toFixed(3)}</td>
                        <td className="px-3 py-2 text-emerald-400">${Number(f.salesAmount).toFixed(2)}</td>
                        <td className="px-3 py-2 text-slate-300">${Number(f.pricePerGallon).toFixed(3)}</td>
                        <td className="px-3 py-2 text-slate-400">{String(f.pumpNumber || "—")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {activeTab === "errors" && (
            <div className="space-y-2">
              {!data.errors?.length ? (
                <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-6 text-center text-emerald-400 text-sm">
                  ✅ No errors recorded for this import.
                </div>
              ) : (
                data.errors.map((e, i) => (
                  <div key={i} className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-4 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-rose-400 uppercase tracking-wider">{e.errorType}</span>
                      {e.field && (
                        <span className="text-xs font-mono text-slate-500 bg-slate-800 px-2 py-0.5 rounded">{e.field}</span>
                      )}
                    </div>
                    <p className="text-sm text-slate-300">{e.message}</p>
                    <p className="text-[10px] text-slate-600">{new Date(e.createdAt).toLocaleString()}</p>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* Raw XML Preview */}
        {data.rawXml && (
          <div className="space-y-2">
            <button
              onClick={() => setShowRaw(x => !x)}
              className="text-xs text-slate-500 hover:text-sky-400 transition-colors flex items-center gap-2"
            >
              <span className={`transition-transform ${showRaw ? "rotate-90" : ""}`}>▶</span>
              {showRaw ? "Hide" : "Show"} Raw XML
            </button>
            {showRaw && (
              <pre className="bg-slate-900/80 border border-white/5 rounded-xl p-4 text-[10px] text-emerald-300 overflow-x-auto max-h-80 font-mono leading-relaxed">
                {data.rawXml.slice(0, 8000)}{data.rawXml.length > 8000 ? "\n\n[...truncated...]" : ""}
              </pre>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
