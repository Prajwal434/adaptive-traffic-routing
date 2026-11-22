import { useEffect, useRef } from 'react'
import L from 'leaflet'

// Density 0→1 maps to green→red
function densityColor(density) {
  if (density < 0.3) return '#22c55e'
  if (density < 0.6) return '#f59e0b'
  return '#ef4444'
}

// Draw a blinking traffic light circle on the map
function trafficLightIcon(color) {
  return L.divIcon({
    className: '',
    html: `<div style="
      width:18px;height:18px;border-radius:50%;
      background:${color};border:2px solid #fff;
      box-shadow:0 0 8px ${color};
    "></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  })
}

function userIcon(color, label) {
  return L.divIcon({
    className: '',
    html: `<div style="
      background:${color};color:#fff;
      border-radius:50%;width:30px;height:30px;
      display:flex;align-items:center;justify-content:center;
      font-size:11px;font-weight:700;border:2px solid #fff;
      box-shadow:0 2px 8px rgba(0,0,0,0.5);
    ">${label}</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  })
}

export default function TrafficMap({ worldState }) {
  const mapRef = useRef(null)
  const layersRef = useRef({ routes: [], segments: [], lights: [], userMarkers: [] })

  // Init map once
  useEffect(() => {
    if (mapRef.current) return
    const map = L.map('map', {
      center: [12.9230, 77.6150],
      zoom: 14,
      zoomControl: true,
    })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 18,
    }).addTo(map)
    mapRef.current = map
  }, [])

  // Update layers on every worldState push
  useEffect(() => {
    const map = mapRef.current
    if (!map || !worldState) return

    const { nodes, segments, users } = worldState
    const layers = layersRef.current

    // Clear previous dynamic layers
    layers.routes.forEach(l => map.removeLayer(l))
    layers.segments.forEach(l => map.removeLayer(l))
    layers.lights.forEach(l => map.removeLayer(l))
    layers.userMarkers.forEach(l => map.removeLayer(l))
    layers.routes = []
    layers.segments = []
    layers.lights = []
    layers.userMarkers = []

    // Draw segment density lines (background road graph)
    const EDGE_PAIRS = [
      ['A','B'],['A','C'],['B','D'],['C','D'],['B','E'],['E','D']
    ]
    EDGE_PAIRS.forEach(([u, v]) => {
      const segId = `${u}-${v}`
      const seg = segments[segId]
      const density = seg ? seg.density : 0
      const nu = nodes[u], nv = nodes[v]
      if (!nu || !nv) return
      const line = L.polyline(
        [[nu.lat, nu.lon], [nv.lat, nv.lon]],
        { color: densityColor(density), weight: 6, opacity: 0.5 }
      ).addTo(map)
      line.bindTooltip(
        `${segId} · density ${Math.round(density * 100)}%` +
        (seg ? ` · ${seg.avg_speed_kmh} km/h · ${seg.vehicle_count} vehicles` : ''),
        { sticky: true }
      )
      layers.segments.push(line)

      // Traffic light at midpoint of dense segments
      if (density > 0.5) {
        const midLat = (nu.lat + nv.lat) / 2
        const midLon = (nu.lon + nv.lon) / 2
        const lightColor = density > 0.75 ? '#ef4444' : '#f59e0b'
        const marker = L.marker([midLat, midLon], {
          icon: trafficLightIcon(lightColor)
        }).addTo(map)
        marker.bindTooltip(`Signal at ${segId}: ${density > 0.75 ? '🔴 RED' : '🟡 AMBER'}`, { sticky: true })
        layers.lights.push(marker)
      }
    })

    // Node labels
    if (nodes) {
      Object.entries(nodes).forEach(([id, pos]) => {
        const circle = L.circleMarker([pos.lat, pos.lon], {
          radius: 8, color: '#fff', fillColor: '#1e293b', fillOpacity: 1, weight: 2
        }).addTo(map)
        circle.bindTooltip(id, { permanent: true, direction: 'top', offset: [0, -6],
          className: 'node-label' })
        layers.segments.push(circle)
      })
    }

    // Draw user routes
    users?.forEach((user, idx) => {
      if (!user.route?.coords) return
      const coords = user.route.coords.map(([lat, lon]) => [lat, lon])
      const isAlternate = user.route.path?.join('') !== ['A','B','D'].join('')

      const routeLine = L.polyline(coords, {
        color: user.color || '#3b82f6',
        weight: isAlternate ? 4 : 5,
        opacity: 0.9,
        dashArray: isAlternate ? '8 6' : null,
      }).addTo(map)
      routeLine.bindTooltip(
        `${user.name} · ${user.assigned_eta_minutes} min` +
        (user.conflict_detected ? ' ⚠ conflict' : ''),
        { sticky: true }
      )
      layers.routes.push(routeLine)

      // User marker at origin
      const origin = user.route.coords[0]
      const label = idx === 0 ? 'P' : 'R'
      const marker = L.marker([origin[0], origin[1]], {
        icon: userIcon(user.color || '#3b82f6', label)
      }).addTo(map)
      marker.bindTooltip(user.name, { permanent: false })
      layers.userMarkers.push(marker)
    })
  }, [worldState])

  return (
    <div id="map" style={{
      width: '100%',
      height: '100%',
      borderRadius: '8px',
    }} />
  )
}
