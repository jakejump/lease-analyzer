import { useEffect, useState } from "react";
import { useRouter } from "next/router";

type Status = { id: string; status: string; stage?: string | null; progress?: number | null; created_at?: string | null };
type Risk = { payload: Record<string, { score: number | null; explanation: string }>; model?: string | null; created_at?: string | null };
type Abnormality = { text: string; impact: "beneficial" | "harmful" | "neutral" };
type Abnorm = { payload: Abnormality[]; model?: string | null; created_at?: string | null };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export default function VersionDetail() {
  const router = useRouter();
  const { id, versionId } = router.query;
  const [status, setStatus] = useState<Status | null>(null);
  const [risk, setRisk] = useState<Risk | null>(null);
  const [abnorm, setAbnorm] = useState<Abnorm | null>(null);
  const [topic, setTopic] = useState("");
  const [clauses, setClauses] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");

  const pollStatus = async () => {
    const res = await fetch(`${API_BASE}/v1/versions/${versionId}/status`);
    const data = await res.json();
    setStatus(data);
  };

  const fetchRisk = async () => {
    const res = await fetch(`${API_BASE}/v1/versions/${versionId}/risk`);
    setRisk(await res.json());
  };

  const fetchAbnorm = async () => {
    const res = await fetch(`${API_BASE}/v1/versions/${versionId}/abnormalities`);
    setAbnorm(await res.json());
  };

  const fetchClauses = async () => {
    const form = new FormData();
    form.append("topic", topic);
    const res = await fetch(`${API_BASE}/v1/versions/${versionId}/clauses`, { method: "POST", body: form });
    const data = await res.json();
    setClauses(data?.clauses || []);
  };

  const ask = async () => {
    const form = new FormData();
    form.append("question", question);
    const res = await fetch(`${API_BASE}/v1/versions/${versionId}/ask`, { method: "POST", body: form });
    const data = await res.json();
    setAnswer(data?.answer || "");
  };

  useEffect(() => {
    if (!versionId) return;
    pollStatus();
    fetchRisk();
    fetchAbnorm();
    const t = setInterval(pollStatus, 3000);
    return () => clearInterval(t);
  }, [versionId]);

  return (
    <main className="min-h-screen p-6 space-y-6">
      <a className="text-blue-600 underline" href={`/projects/${id}`}>← Back</a>
      <h1 className="text-2xl font-semibold">Version {versionId}</h1>

      <div className="border p-4 rounded">
        <div>Status: {status?.status} {status?.stage ? `• ${status.stage}` : ""} {status?.progress ? `• ${status.progress}%` : ""}</div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="border p-4 rounded">
          <h2 className="font-medium mb-2">Risk</h2>
          <pre className="whitespace-pre-wrap text-sm">{JSON.stringify(risk?.payload || {}, null, 2)}</pre>
        </div>
        <div className="border p-4 rounded">
          <h2 className="font-medium mb-2">Abnormalities</h2>
          <ul className="list-disc pl-6 text-sm">
            {(abnorm?.payload || []).map((a, i) => (
              <li key={i} className={a.impact === "beneficial" ? "text-green-600" : a.impact === "neutral" ? "text-yellow-600" : "text-red-600"}>{a.text}</li>
            ))}
          </ul>
        </div>
      </div>

      <div className="border p-4 rounded">
        <h2 className="font-medium mb-2">Clauses</h2>
        <div className="flex gap-2 mb-2">
          <input className="border p-2 flex-1" placeholder="Topic (e.g., cash_flow_adjustments)" value={topic} onChange={(e) => setTopic(e.target.value)} />
          <button className="bg-blue-600 text-white px-3 py-2 rounded" onClick={fetchClauses}>Fetch</button>
        </div>
        <ul className="list-disc pl-6 space-y-1">
          {clauses.map((c, i) => (
            <li key={i}><div className="whitespace-pre-wrap">{c}</div></li>
          ))}
        </ul>
      </div>

      <div className="border p-4 rounded">
        <h2 className="font-medium mb-2">Ask</h2>
        <div className="flex gap-2 mb-2">
          <input className="border p-2 flex-1" placeholder="Your question" value={question} onChange={(e) => setQuestion(e.target.value)} />
          <button className="bg-blue-600 text-white px-3 py-2 rounded" onClick={ask}>Ask</button>
        </div>
        {answer && <div className="whitespace-pre-wrap">{answer}</div>}
      </div>
    </main>
  );
}


