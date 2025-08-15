import { useEffect, useState } from "react";
import { useRouter } from "next/router";

type Version = { id: string; label?: string | null; status: string };
type Change = { type: "added" | "removed" | "modified"; clause_no?: string | null; before?: string | null; after?: string | null };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export default function DiffPage() {
  const router = useRouter();
  const { id } = router.query;
  const [versions, setVersions] = useState<Version[]>([]);
  const [baseId, setBaseId] = useState<string>("");
  const [compareId, setCompareId] = useState<string>("");
  const [changes, setChanges] = useState<Change[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    (async () => {
      const res = await fetch(`${API_BASE}/v1/projects/${id}/versions`);
      const data = await res.json();
      setVersions(data || []);
    })();
  }, [id]);

  const runDiff = async () => {
    if (!baseId || !compareId) return;
    setLoading(true);
    const form = new FormData();
    form.append("base_version_id", baseId);
    form.append("compare_version_id", compareId);
    const res = await fetch(`${API_BASE}/v1/diff`, { method: "POST", body: form });
    const data = await res.json();
    setChanges(data?.changes || []);
    setLoading(false);
  };

  return (
    <main className="min-h-screen p-6 space-y-4">
      <a className="text-blue-600 underline" href={`/projects/${id}`}>← Back</a>
      <h1 className="text-2xl font-semibold">Diff</h1>
      <div className="flex gap-3 items-end">
        <div>
          <label className="block text-sm">Base</label>
          <select className="border p-2" value={baseId} onChange={(e) => setBaseId(e.target.value)}>
            <option value="">Select version</option>
            {versions.map((v) => (
              <option key={v.id} value={v.id}>{v.label || v.id}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm">Compare</label>
          <select className="border p-2" value={compareId} onChange={(e) => setCompareId(e.target.value)}>
            <option value="">Select version</option>
            {versions.map((v) => (
              <option key={v.id} value={v.id}>{v.label || v.id}</option>
            ))}
          </select>
        </div>
        <button className="bg-blue-600 text-white px-3 py-2 rounded" onClick={runDiff} disabled={loading || !baseId || !compareId}>
          {loading ? "Computing..." : "Run Diff"}
        </button>
      </div>

      <div className="space-y-3">
        {changes.map((c, i) => (
          <div key={i} className="border rounded p-3">
            <div className="text-sm text-gray-700 mb-2">
              <span className={c.type === "added" ? "text-green-700" : c.type === "removed" ? "text-red-700" : "text-yellow-700"}>
                {c.type.toUpperCase()}
              </span>
              {c.clause_no ? ` • Clause ${c.clause_no}` : ""}
            </div>
            {c.before && (
              <div className="mb-2">
                <div className="text-xs text-gray-500">Before</div>
                <div className="whitespace-pre-wrap text-sm">{c.before}</div>
              </div>
            )}
            {c.after && (
              <div>
                <div className="text-xs text-gray-500">After</div>
                <div className="whitespace-pre-wrap text-sm">{c.after}</div>
              </div>
            )}
          </div>
        ))}
      </div>
    </main>
  );
}


