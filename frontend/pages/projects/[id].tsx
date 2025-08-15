import { useEffect, useState } from "react";
import { useRouter } from "next/router";

type Project = { id: string; name: string; description?: string | null; current_version_id?: string | null };
type Version = { id: string; label?: string | null; status: string; created_at?: string | null };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export default function ProjectDetail() {
  const router = useRouter();
  const { id } = router.query;
  const [project, setProject] = useState<Project | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [label, setLabel] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [settingCurrent, setSettingCurrent] = useState<string | null>(null);

  const loadProject = async () => {
    const res = await fetch(`${API_BASE}/v1/projects/${id}`);
    setProject(await res.json());
  };

  const loadVersions = async () => {
    const res = await fetch(`${API_BASE}/v1/projects/${id}/versions`);
    setVersions(await res.json());
  };

  useEffect(() => {
    if (!id) return;
    loadProject();
    loadVersions();
  }, [id]);

  const uploadVersion = async () => {
    if (!file) return;
    setUploading(true);
    const form = new FormData();
    form.append("label", label);
    form.append("file", file);
    await fetch(`${API_BASE}/v1/projects/${id}/versions/upload`, { method: "POST", body: form });
    setLabel("");
    setFile(null);
    await loadVersions();
    setUploading(false);
  };

  const setCurrent = async (versionId: string) => {
    setSettingCurrent(versionId);
    const form = new FormData();
    form.append("current_version_id", versionId);
    await fetch(`${API_BASE}/v1/projects/${id}`, { method: "PATCH", body: form });
    await loadProject();
    setSettingCurrent(null);
  };

  return (
    <main className="min-h-screen p-6 space-y-4">
      <a className="text-blue-600 underline" href="/projects">← Back</a>
      <h1 className="text-2xl font-semibold">{project?.name || "Project"}</h1>
      {project?.description && <p className="text-gray-700">{project.description}</p>}
      <div>
        <a className="text-blue-600 underline" href={`/projects/${id}/diff`}>Compare Versions (Diff)</a>
      </div>

      <div className="border p-4 rounded">
        <h2 className="font-medium mb-2">Upload Version</h2>
        <input className="border p-2 mr-2" placeholder="Label (optional)" value={label} onChange={(e) => setLabel(e.target.value)} />
        <input className="border p-2 mr-2" type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        <button className="bg-blue-600 text-white px-3 py-2 rounded" onClick={uploadVersion} disabled={uploading || !file}>
          {uploading ? "Uploading..." : "Upload"}
        </button>
      </div>

      <div>
        <h2 className="font-medium mb-2">Versions</h2>
        <ul className="space-y-2">
          {versions.map((v) => (
            <li key={v.id} className="border p-3 rounded">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium">{v.label || v.id}</div>
                  <div className="text-sm text-gray-600">Status: {v.status} {v.created_at ? `• ${v.created_at}` : ""}</div>
                  {project?.current_version_id === v.id && (
                    <div className="text-xs text-green-700">Current</div>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <a className="text-blue-600 underline" href={`/projects/${id}/versions/${v.id}`}>Open</a>
                  <button
                    className="bg-gray-200 px-2 py-1 rounded"
                    onClick={() => setCurrent(v.id)}
                    disabled={settingCurrent === v.id}
                  >
                    {settingCurrent === v.id ? "Setting..." : "Set Current"}
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}


