"use client";

import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { Activity, Shield, Zap, TrendingUp } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Run {
  run_id: string;
  status: string;
  tx_hash?: string;
  block?: number;
  old_fee?: number;
  new_fee?: number;
  confidence?: number;
  reasoning?: string;
  eth_price?: number;
  data_quality?: number;
  proof_type?: string;
}

interface Stats {
  total_runs: number;
  executed: number;
  skipped: number;
  avg_confidence: number;
  latest_fee: number;
  latest_tx: string | null;
}

export default function Dashboard() {
  const [history, setHistory]   = useState<Run[]>([]);
  const [stats, setStats]       = useState<Stats | null>(null);
  const [latest, setLatest]     = useState<Run | null>(null);
  const [triggering, setTriggering] = useState(false);

  const fetchData = async () => {
    try {
      const [h, s, l] = await Promise.all([
        fetch(`${API}/v1/contracts/history?limit=20`).then(r => r.json()),
        fetch(`${API}/v1/contracts/stats`).then(r => r.json()),
        fetch(`${API}/v1/contracts/latest-run`).then(r => r.json()),
      ]);
      setHistory(h);
      setStats(s);
      setLatest(l);
    } catch (_) {}
  };

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, 15_000);
    return () => clearInterval(id);
  }, []);

  const trigger = async () => {
    setTriggering(true);
    await fetch(`${API}/v1/contracts/trigger`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "manual_demo_trigger" }),
    });
    setTimeout(() => { fetchData(); setTriggering(false); }, 5000);
  };

  const feeHistory = history
    .filter(r => r.new_fee)
    .map(r => ({ fee: r.new_fee, eth: r.eth_price, run: r.run_id?.slice(-6) }))
    .reverse();

  const feePercent = (bps?: number) => bps ? `${(bps / 100).toFixed(2)}%` : "—";

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6 font-mono">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">LivingContract OS</h1>
          <p className="text-gray-400 text-sm mt-1">AI-Governed Smart Contract Engine · Sepolia Testnet</p>
        </div>
        <button
          onClick={trigger}
          disabled={triggering}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 rounded-lg text-sm font-medium transition-colors"
        >
          <Zap size={14} />
          {triggering ? "Running..." : "Trigger Agent"}
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard icon={<TrendingUp size={16}/>} label="Current Fee"
          value={feePercent(stats?.latest_fee)} sub="basis points" />
        <StatCard icon={<Activity size={16}/>} label="Total Runs"
          value={String(stats?.total_runs ?? 0)} sub={`${stats?.executed ?? 0} executed`} />
        <StatCard icon={<Shield size={16}/>} label="Avg Confidence"
          value={stats ? `${(stats.avg_confidence * 100).toFixed(1)}%` : "—"} sub="LLM certainty" />
        <StatCard icon={<Zap size={16}/>} label="Policy Boundary"
          value="4.25% – 5.75%" sub="AI-enforced on-chain" />
      </div>

      {/* Chart + Latest */}
      <div className="grid md:grid-cols-2 gap-6 mb-6">
        {/* Fee history chart */}
        <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
          <h2 className="text-sm text-gray-400 mb-4">Fee History (basis points)</h2>
          {feeHistory.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={feeHistory}>
                <XAxis dataKey="run" tick={{ fontSize: 10, fill: "#6b7280" }} />
                <YAxis domain={[420, 580]} tick={{ fontSize: 10, fill: "#6b7280" }} />
                <Tooltip
                  contentStyle={{ background: "#111827", border: "1px solid #374151", fontSize: 12 }}
                  formatter={(v: number) => [`${v} bps (${(v/100).toFixed(2)}%)`, "Fee"]}
                />
                <ReferenceLine y={425} stroke="#ef4444" strokeDasharray="3 3" label={{ value: "min", fill: "#ef4444", fontSize: 10 }} />
                <ReferenceLine y={575} stroke="#ef4444" strokeDasharray="3 3" label={{ value: "max", fill: "#ef4444", fontSize: 10 }} />
                <ReferenceLine y={500} stroke="#6b7280" strokeDasharray="2 2" />
                <Line type="monotone" dataKey="fee" stroke="#6366f1" strokeWidth={2} dot={{ fill: "#6366f1", r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[180px] flex items-center justify-center text-gray-600 text-sm">
              No data yet — trigger the agent
            </div>
          )}
        </div>

        {/* Latest run */}
        <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
          <h2 className="text-sm text-gray-400 mb-4">Latest Agent Decision</h2>
          {latest && latest.status !== "no_runs_yet" ? (
            <div className="space-y-3 text-sm">
              <Row label="Status" value={
                <span className={`px-2 py-0.5 rounded text-xs ${
                  latest.status === "executed" ? "bg-green-900 text-green-300" :
                  latest.status === "skipped"  ? "bg-yellow-900 text-yellow-300" :
                  "bg-red-900 text-red-300"
                }`}>{latest.status}</span>
              }/>
              <Row label="Fee" value={`${feePercent(latest.old_fee)} → ${feePercent(latest.new_fee)}`} />
              <Row label="Confidence" value={latest.confidence ? `${(latest.confidence*100).toFixed(1)}%` : "—"} />
              <Row label="ETH Price" value={latest.eth_price ? `$${latest.eth_price.toLocaleString()}` : "—"} />
              <Row label="Data Quality" value={latest.data_quality ? `${(latest.data_quality*100).toFixed(0)}%` : "—"} />
              <Row label="Proof" value={<span className="text-indigo-400">{latest.proof_type ?? "—"}</span>} />
              {latest.tx_hash && (
                <Row label="Tx" value={
                  <a
                    href={`https://sepolia.etherscan.io/tx/${latest.tx_hash}`}
                    target="_blank" rel="noreferrer"
                    className="text-indigo-400 hover:underline"
                  >{latest.tx_hash.slice(0,10)}...{latest.tx_hash.slice(-8)}</a>
                }/>
              )}
              {latest.reasoning && (
                <div className="mt-3 p-3 bg-gray-800 rounded-lg text-gray-300 text-xs leading-relaxed">
                  {latest.reasoning}
                </div>
              )}
            </div>
          ) : (
            <div className="h-full flex items-center justify-center text-gray-600 text-sm">
              No decisions yet
            </div>
          )}
        </div>
      </div>

      {/* Run history table */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-800">
          <h2 className="text-sm text-gray-400">Decision Audit Trail</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="px-4 py-2 text-left">Run</th>
                <th className="px-4 py-2 text-left">Status</th>
                <th className="px-4 py-2 text-right">Fee</th>
                <th className="px-4 py-2 text-right">ETH Price</th>
                <th className="px-4 py-2 text-right">Confidence</th>
                <th className="px-4 py-2 text-left">Tx Hash</th>
              </tr>
            </thead>
            <tbody>
              {history.map((r, i) => (
                <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="px-4 py-2 text-gray-500">{r.run_id?.slice(-8)}</td>
                  <td className="px-4 py-2">
                    <span className={`px-1.5 py-0.5 rounded text-xs ${
                      r.status === "executed" ? "bg-green-900/50 text-green-400" :
                      r.status === "no_change" ? "bg-gray-800 text-gray-400" :
                      "bg-yellow-900/50 text-yellow-400"
                    }`}>{r.status}</span>
                  </td>
                  <td className="px-4 py-2 text-right text-gray-300">
                    {r.new_fee ? feePercent(r.new_fee) : "—"}
                  </td>
                  <td className="px-4 py-2 text-right text-gray-300">
                    {r.eth_price ? `$${r.eth_price.toLocaleString()}` : "—"}
                  </td>
                  <td className="px-4 py-2 text-right text-gray-300">
                    {r.confidence ? `${(r.confidence*100).toFixed(0)}%` : "—"}
                  </td>
                  <td className="px-4 py-2 text-indigo-400">
                    {r.tx_hash ? (
                      <a href={`https://sepolia.etherscan.io/tx/${r.tx_hash}`} target="_blank" rel="noreferrer" className="hover:underline">
                        {r.tx_hash.slice(0,8)}...
                      </a>
                    ) : "—"}
                  </td>
                </tr>
              ))}
              {history.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-600">
                    No runs yet — trigger the agent above
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string; sub: string }) {
  return (
    <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
      <div className="flex items-center gap-2 text-gray-400 text-xs mb-2">
        {icon} {label}
      </div>
      <div className="text-xl font-bold text-white">{value}</div>
      <div className="text-gray-500 text-xs mt-1">{sub}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between items-start">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-200 text-right max-w-[60%]">{value}</span>
    </div>
  );
}
