/** PIN code, state, district and road for a report's pin, from OpenStreetMap's public address lookup. Reports only store the
 *  coordinates, so this is the nearest known address to the pin. One request per report opened, remembered for the visit. */
export interface Address {
  road?: string;
  area?: string;
  city?: string;
  district?: string;
  state?: string;
  pin?: string;
}

const known = new Map<string, Promise<Address | null>>();

export function lookupAddress(lat: number, lng: number): Promise<Address | null> {
  const key = `${lat.toFixed(5)},${lng.toFixed(5)}`;
  let found = known.get(key);
  if (!found) {
    const url = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=18&addressdetails=1&accept-language=en&lat=${lat}&lon=${lng}`;
    found = fetch(url)
      .then((res) => (res.ok ? res.json() : null))
      .then((j) => {
        const a = j?.address;
        if (!a) return null;
        return {
          road: a.road,
          area: a.suburb ?? a.neighbourhood ?? a.village ?? a.hamlet ?? a.quarter,
          city: a.city ?? a.town ?? a.municipality,
          district: a.state_district ?? a.county ?? a.city_district,
          state: a.state ?? a.territory,
          pin: a.postcode,
        } as Address;
      })
      .catch(() => null);
    known.set(key, found);
  }
  return found;
}
