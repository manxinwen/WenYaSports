/** 前端展示格式化工具 */

/** 秒 -> "HH:MM:SS" / "MM:SS" */
export function formatDuration(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return '-';
  const s = Math.round(Number(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const mm = String(m).padStart(2, '0');
  const ss = String(sec).padStart(2, '0');
  return h > 0 ? `${h}:${mm}:${ss}` : `${m}:${ss}`;
}

/** 配速(分钟/公里) -> "mm:ss /km" */
export function formatPace(minPerKm) {
  if (minPerKm == null || Number.isNaN(minPerKm)) return '-';
  const totalSeconds = Math.round(Number(minPerKm) * 60);
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')} /km`;
}

/** 米 -> "x.xx km" */
export function formatDistance(meters) {
  if (meters == null || Number.isNaN(meters)) return '-';
  return `${(Number(meters) / 1000).toFixed(2)} km`;
}

/** 海拔/爬升(米) -> "x m" */
export function formatMeters(m) {
  if (m == null || Number.isNaN(m)) return '-';
  return `${Number(m).toFixed(0)} m`;
}

/** 心率值 */
export function formatHr(hr) {
  return hr == null ? '-' : String(hr);
}

/** 日期 -> "YYYY-MM-DD HH:mm" */
export function formatDateTime(iso) {
  if (!iso) return '-';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}`;
}

/** 运动类型展示 */
export function formatSport(sport) {
  const map = {
    running: '跑步',
    cycling: '骑行',
    swimming: '游泳',
    walking: '步行',
    hiking: '徒步',
  };
  return map[sport] || sport || '未知';
}
