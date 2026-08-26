import { CircleMarker, MapContainer, Polyline, Popup, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

/** 基于活动轨迹点绘制 Leaflet 地图 */
export default function ActivityMap({ records, height = 380 }) {
  const positions = (records || [])
    .filter((r) => r.lat != null && r.lon != null)
    .map((r) => [r.lat, r.lon]);

  if (positions.length === 0) {
    return (
      <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999' }}>
        该活动没有轨迹数据
      </div>
    );
  }

  const start = positions[0];
  const end = positions[positions.length - 1];

  return (
    <MapContainer
      center={start}
      zoom={14}
      style={{ height, width: '100%', borderRadius: 8 }}
      scrollWheelZoom={false}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Polyline
        positions={positions}
        pathOptions={{ color: '#1677ff', weight: 4, opacity: 0.85 }}
      />
      <CircleMarker
        center={start}
        radius={6}
        pathOptions={{ color: '#52c41a', fillColor: '#52c41a', fillOpacity: 1 }}
      >
        <Popup>起点</Popup>
      </CircleMarker>
      <CircleMarker
        center={end}
        radius={6}
        pathOptions={{ color: '#ff4d4f', fillColor: '#ff4d4f', fillOpacity: 1 }}
      >
        <Popup>终点</Popup>
      </CircleMarker>
    </MapContainer>
  );
}
