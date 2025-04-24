import Head from 'next/head';
import LeaseQA from '../components/LeaseQA';

export default function Home() {
  return (
    <>
      <Head>
        <title>Lease Analyzer</title>
      </Head>
      <main className="min-h-screen bg-gray-200 p-8">
        <div className="max-w-5xl mx-auto bg-gray-800 rounded-lg shadow p-6">
          <h1 className="text-2xl font-bold mb-4">Lease.AI</h1>
          <LeaseQA />
        </div>
      </main>
    </>
  );
}
