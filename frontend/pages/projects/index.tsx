import { useEffect, useState } from "react";

type Project = {
  id: string;
  name: string;
  description?: string | null;
  current_version_id?: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);

  const loadProjects = async () => {
    const res = await fetch(`${API_BASE}/v1/projects`);
    const data = await res.json();
    setProjects(data || []);
  };

  useEffect(() => {
    loadProjects();
  }, []);

  const createProject = async () => {
    if (!name.trim()) return;
    setLoading(true);
    await fetch(`${API_BASE}/v1/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description }),
    });
    setName("");
    setDescription("");
    await loadProjects();
    setLoading(false);
  };

  return (
    <main className="min-h-screen p-6">
      <h1 className="text-2xl font-semibold mb-4">Projects</h1>
      <div className="border p-4 rounded mb-6">
        <h2 className="font-medium mb-2">Create Project</h2>
        <input
          className="border p-2 mr-2"
          placeholder="Project name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="border p-2 mr-2"
          placeholder="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <button className="bg-blue-600 text-white px-3 py-2 rounded" onClick={createProject} disabled={loading}>
          {loading ? "Creating..." : "Create"}
        </button>
      </div>

      <ul className="space-y-3">
        {projects.map((p) => (
          <li key={p.id} className="border rounded p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium">{p.name}</div>
                {p.description && <div className="text-sm text-gray-600">{p.description}</div>}
              </div>
              <a className="text-blue-600 underline" href={`/projects/${p.id}`}>Open</a>
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}


