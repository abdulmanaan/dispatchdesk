// Lahore neighbourhoods with approximate centre coordinates. Used instead of a
// maps API: people pick an area and type the street address themselves.

export interface Area {
  name: string
  lat: number
  lng: number
}

export const LAHORE_AREAS: Area[] = [
  { name: 'Anarkali', lat: 31.568, lng: 74.311 },
  { name: 'Bahria Town', lat: 31.37, lng: 74.18 },
  { name: 'Cantt', lat: 31.518, lng: 74.392 },
  { name: 'DHA Phase 5', lat: 31.465, lng: 74.409 },
  { name: 'Faisal Town', lat: 31.479, lng: 74.303 },
  { name: 'Garden Town', lat: 31.504, lng: 74.331 },
  { name: 'Gulberg', lat: 31.516, lng: 74.348 },
  { name: 'Iqbal Town', lat: 31.5106, lng: 74.286 },
  { name: 'Johar Town', lat: 31.471, lng: 74.281 },
  { name: 'Liberty Market', lat: 31.5104, lng: 74.3416 },
  { name: 'Model Town', lat: 31.484, lng: 74.322 },
  { name: 'Shadman', lat: 31.539, lng: 74.329 },
  { name: 'Township', lat: 31.4475, lng: 74.307 },
  { name: 'Wapda Town', lat: 31.438, lng: 74.265 },
]

export function findArea(name: string): Area | undefined {
  return LAHORE_AREAS.find((area) => area.name === name)
}

/** The named area closest to a point (for "you are near Gulberg" labels). */
export function nearestArea(lat: number, lng: number): Area {
  return LAHORE_AREAS.reduce((best, area) =>
    (area.lat - lat) ** 2 + (area.lng - lng) ** 2 < (best.lat - lat) ** 2 + (best.lng - lng) ** 2
      ? area
      : best,
  )
}
