import { useEffect, useState } from "react";

export default function SystemMonitor() {
  const [stats, setStats] = useState({
    cpu: 66.3,
    memoryUsed: 1.1,
    memoryTotal: 7.4,
    diskUsed: 103.7,
    diskTotal: 1006.9,
  });

  useEffect(() => {
    const interval = setInterval(() => {
      setStats((prev) => ({
        ...prev,
        cpu: Math.min(100, Math.max(0, prev.cpu + (Math.random() - 0.5) * 10)),
      }));
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-slate-900 text-white rounded-2xl shadow-lg p-5 sm:p-6 w-full max-w-6xl mx-auto mt-4">
      <h2 className="text-lg sm:text-xl font-semibold mb-3 flex items-center gap-2">
        <span className="text-yellow-400">💻</span> System Monitor
      </h2>

      <div className="space-y-2 sm:space-y-3 text-sm sm:text-base">
        {/* CPU */}
        <div>
          <p>
            CPU Usage:{" "}
            <span className="text-yellow-400 font-semibold">
              {stats.cpu.toFixed(1)}%
            </span>
          </p>
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className="bg-green-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${stats.cpu}%` }}
            />
          </div>
        </div>

        {/* Memory */}
        <div>
          <p>
            Memory:{" "}
            <span className="text-blue-400 font-semibold">
              {((stats.memoryUsed / stats.memoryTotal) * 100).toFixed(1)}%
            </span>{" "}
            ({stats.memoryUsed} GB / {stats.memoryTotal} GB)
          </p>
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-300"
              style={{
                width: `${(stats.memoryUsed / stats.memoryTotal) * 100}%`,
              }}
            />
          </div>
        </div>

        {/* Disk */}
        <div>
          <p>
            Disk:{" "}
            <span className="text-orange-400 font-semibold">
              {((stats.diskUsed / stats.diskTotal) * 100).toFixed(1)}%
            </span>{" "}
            ({stats.diskUsed} GB / {stats.diskTotal} GB)
          </p>
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className="bg-orange-500 h-2 rounded-full transition-all duration-300"
              style={{
                width: `${(stats.diskUsed / stats.diskTotal) * 100}%`,
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
