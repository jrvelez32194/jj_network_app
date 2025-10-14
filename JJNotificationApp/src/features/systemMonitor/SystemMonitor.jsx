import { useGetSystemStatusQuery } from "../api/systemMonitorApi";

export default function SystemMonitor() {
  const {
    data: stats,
    isLoading,
    isError,
  } = useGetSystemStatusQuery(undefined, { pollingInterval: 10000 });

  if (isLoading) {
    return (
      <div className="bg-slate-900 text-white rounded-2xl shadow-lg p-6 w-full max-w-6xl mx-auto mt-4 text-center">
        <p className="text-gray-400">Loading system stats...</p>
      </div>
    );
  }

  if (isError || !stats) {
    return (
      <div className="bg-slate-900 text-white rounded-2xl shadow-lg p-6 w-full max-w-6xl mx-auto mt-4 text-center">
        <p className="text-red-400">Failed to fetch system status.</p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 text-white rounded-2xl shadow-lg p-5 sm:p-6 w-full max-w-6xl mx-auto mt-4">
      <h2 className="text-lg sm:text-xl font-semibold mb-3 flex items-center gap-2">
        <span className="text-yellow-400">💻</span> System Monitor
      </h2>

      <div className="space-y-3 text-sm sm:text-base">
        {/* CPU */}
        <div>
          <p>
            CPU Usage:{" "}
            <span className="text-yellow-400 font-semibold">
              {stats.cpu?.toFixed(1)}%
            </span>{" "}
            {stats.temperature && (
              <span className="ml-2 text-gray-300">
                | Temp:{" "}
                <span className="text-red-400 font-semibold">
                  {stats.temperature.toFixed(1)}°C
                </span>
              </span>
            )}
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
              {stats.memory.percent.toFixed(1)}%
            </span>{" "}
            ({stats.memory.used.toFixed(1)} GB / {stats.memory.total.toFixed(1)}{" "}
            GB)
          </p>
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${stats.memory.percent}%` }}
            />
          </div>
        </div>

        {/* Disk */}
        <div>
          <p>
            Disk:{" "}
            <span className="text-orange-400 font-semibold">
              {stats.disk.percent.toFixed(1)}%
            </span>{" "}
            ({stats.disk.used.toFixed(1)} GB / {stats.disk.total.toFixed(1)} GB)
          </p>
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className="bg-orange-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${stats.disk.percent}%` }}
            />
          </div>
        </div>

        {/* Extra Info */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-3 text-gray-300 text-sm">
          <p>
            🕒 <span className="text-green-400">Uptime:</span>{" "}
            {stats.uptime || "N/A"}
          </p>
          <p>
            🔁 <span className="text-cyan-400">ZRAM:</span>{" "}
            {stats.zram?.percent?.toFixed(1)}% of{" "}
            {stats.zram?.total?.toFixed(1)} MB
          </p>
          <p>
            📡 <span className="text-purple-400">RX Today:</span>{" "}
            {stats.rx_today || "0 GiB"}
          </p>
        </div>
      </div>
    </div>
  );
}
