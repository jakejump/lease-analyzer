import { useState } from 'react';
import axios from 'axios';

interface RiskAssessment {
  score: number | null;
  explanation: string;
}

export default function LeaseQA() {
    const [file, setFile] = useState<File | null>(null);
    const [question, setQuestion] = useState<string>("");
    const [response, setResponse] = useState<string | null>(null);
    const [risks, setRisks] = useState<Record<string, RiskAssessment> | null>(null);
    const [abnormalities, setAbnormalities] = useState<string[]>([]);
    const [loading, setLoading] = useState<boolean>(false);
    const [evaluating, setEvaluating] = useState<boolean>(false);
    const [clauseContext, setClauseContext] = useState<Record<string, string[]>>({});
    const [loadingClauses, setLoadingClauses] = useState<string | null>(null);

    const handleUpload = async () => {
        if (!file) return;
        setEvaluating(true);
        const formData = new FormData();
        formData.append("file", file);

        try {
            const resUpload = await axios.post("https://lease-analyzer-2.onrender.com/upload", formData);
            const parsedRisks = typeof resUpload.data.risks === "string"
                ? JSON.parse(resUpload.data.risks)
                : resUpload.data.risks;
            setRisks(parsedRisks);

            const resAbnormalities = await axios.post("https://lease-analyzer-2.onrender.com/abnormalities");
            const parsedAbnormalities = resAbnormalities.data.abnormalities || [];
            setAbnormalities(parsedAbnormalities);
            console.log("Abnormalities", abnormalities);

        } catch {
            console.error("Failed during upload or abnormalities detection");
            setRisks({});
            setAbnormalities([]);
        } finally {
            setEvaluating(false);
        }
    };

    const handleAsk = async () => {
        setLoading(true);
        const formData = new FormData();
        formData.append("question", question);
        const res = await axios.post("https://lease-analyzer-2.onrender.com/ask", formData);
        setResponse(res.data.answer);
        setLoading(false);
    };

    const handleShowClauses = async (topic: string) => {
        const alreadyVisible = clauseContext[topic]?.length > 0;
        if (alreadyVisible) {
            setClauseContext(prev => {
                const updated = { ...prev };
                delete updated[topic];
                return updated;
            });
            return;
        }
        setLoadingClauses(topic);
        const formData = new FormData();
        formData.append("topic", topic);
        const res = await axios.post("https://lease-analyzer-2.onrender.com/clauses", formData);
        setClauseContext(prev => ({ ...prev, [topic]: res.data.clauses || [] }));
        setLoadingClauses(null);
    };

    const getRiskGradient = (score: number | null): [string, string] => {
        if (score === null) return ["#9CA3AF", "#4B5563"];
        if (score <= 3) return ["#F87171", "#B91C1C"];
        if (score <= 6) return ["#FACC15", "#CA8A04"];
        return ["#4ADE80", "#15803D"];
    };

    return (
        <div className="min-h-screen bg-gray-900 text-gray-100 px-4 py-8">
            <div className="max-w-6xl mx-auto space-y-6">
                <input
                    type="file"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                    className="border border-gray-700 bg-gray-800 p-2 rounded w-full text-white"
                />
                <button
                    onClick={handleUpload}
                    disabled={!file || evaluating}
                    className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
                >
                    {evaluating ? "Evaluating..." : "Upload Lease & Evaluate Risk"}
                </button>

                {evaluating && (
                    <div className="text-center animate-pulse text-blue-400">Loading risk analysis...</div>
                )}

                {risks && (
                    <div className="bg-gray-800 p-4 rounded shadow animate-fade-in">
                        <h2 className="text-lg font-semibold mb-4">Risk Evaluation</h2>
                        <ul className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {Object.entries(risks).map(([category, val]) => {
                                const [start, end] = getRiskGradient(val.score);
                                const isLoading = loadingClauses === category;
                                const clauses = clauseContext[category] || [];
                                return (
                                    <li
                                        key={category}
                                        className="flex flex-col border border-gray-700 rounded p-4 animate-fade-in"
                                    >
                                        <div className="flex justify-between items-start">
                                            <div className="flex-1 pr-4">
                                                <strong className="block mb-1 capitalize">{category.replace(/_/g, ' ')}:</strong>
                                                <em className="text-sm block mb-1">{val.explanation}</em>
                                                <button
                                                    onClick={() => handleShowClauses(category)}
                                                    className="mt-2 px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                                                    disabled={isLoading}
                                                >
                                                    {isLoading ? "Gathering Clauses..." : clauses.length > 0 ? "Hide Clauses" : "Show Clauses"}
                                                </button>
                                            </div>
                                            <div className="relative w-12 h-12">
                                                <div
                                                    className="circular-border"
                                                    style={{ backgroundImage: `conic-gradient(from 0deg, ${start}, ${end})` }}
                                                ></div>
                                                <div className="absolute inset-1 rounded-full bg-gray-900"></div>
                                                <div className="absolute inset-0 flex items-center justify-center font-bold text-sm text-white">
                                                    {val.score ?? "?"}
                                                </div>
                                            </div>
                                        </div>
                                        {clauses.length > 0 && (
                                            <div className="mt-4 text-sm text-gray-300">
                                                <strong className="block mb-1">Relevant Clauses:</strong>
                                                <ul className="list-disc pl-5 space-y-1">
                                                    {clauses.map((text, idx) => (
                                                        <li key={idx}>{text}</li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )}
                                    </li>
                                );
                            })}
                        </ul>
                    </div>
                )}

                {abnormalities.length > 0 && (
                    <div className="bg-gray-800 p-4 rounded shadow animate-fade-in mt-6">
                        <h2 className="text-lg font-semibold mb-4">Abnormalities Found</h2>
                        <ul className="list-disc pl-5 space-y-2 text-red-400">
                            {abnormalities.map((abnormality, idx) => (
                                <li key={idx}>{abnormality}</li>
                            ))}
                        </ul>
                    </div>
                )}

                <div className="space-y-2">
                    <textarea
                        placeholder="Ask a question about the lease..."
                        value={question}
                        onChange={(e) => setQuestion(e.target.value)}
                        className="w-full p-2 border border-gray-700 bg-gray-800 text-white rounded"
                        rows={4}
                    />
                    <button
                        onClick={handleAsk}
                        disabled={loading || !question}
                        className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
                    >
                        {loading ? "Thinking..." : "Ask"}
                    </button>
                </div>

                {response && (
                    <div className="bg-gray-800 p-4 mt-4 rounded whitespace-pre-wrap animate-fade-in">
                        <div className="whitespace-pre-wrap break-words">{response}</div>
                        <button
                            onClick={() => handleShowClauses("user_question")}
                            className="mt-2 px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                            disabled={loadingClauses === "user_question"}
                        >
                            {loadingClauses === "user_question" ? "Gathering Clauses..." : clauseContext["user_question"]?.length > 0 ? "Hide Clauses" : "Show Clauses"}
                        </button>

                        {clauseContext["user_question"]?.length > 0 && (
                            <div className="mt-4 text-sm text-gray-300">
                                <strong className="block mb-1">Relevant Clauses:</strong>
                                <ul className="list-disc pl-5 space-y-1">
                                    {clauseContext["user_question"].map((text, idx) => (
                                        <li key={idx}>{text}</li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                )}
            </div>

            <style jsx global>{`
                @keyframes fade-in {
                    0% { opacity: 0; }
                    100% { opacity: 1; }
                }
                .animate-fade-in {
                    animation: fade-in 1s ease-out forwards;
                }

                @keyframes spin-shine {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }

                .circular-border {
                    width: 3rem;
                    height: 3rem;
                    border-radius: 50%;
                    border: 2px solid transparent;
                    animation: spin-shine 4s linear infinite;
                    position: absolute;
                    inset: 0;
                }
            `}</style>
        </div>
    );
}
