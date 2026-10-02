"""Geographic helpers implemented in plain Python (no maps API)."""

import math
from dataclasses import dataclass

EARTH_RADIUS_KM = 6371.0088  # mean Earth radius
# Length of one degree of latitude on a sphere of that radius (~111.19 km).
KM_PER_DEGREE_LAT = math.pi * EARTH_RADIUS_KM / 180
# The box is a pre-filter, so err on the generous side: exact distances are
# checked afterwards, and a great circle due east/west bulges slightly past a
# box built from parallels.
_BOX_MARGIN = 1.01


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two WGS84 points, in kilometres.

    Straight-line distance, not road distance; good enough to rank nearby drivers.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class BoundingBox:
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float


def bounding_box(lat: float, lng: float, radius_km: float) -> BoundingBox:
    """A lat/lng box that fully contains the circle of ``radius_km`` around a point.

    Used as a cheap, index-friendly SQL pre-filter before exact haversine checks.
    """
    radius_km *= _BOX_MARGIN
    lat_delta = radius_km / KM_PER_DEGREE_LAT
    # Longitude degrees shrink towards the poles; clamp to avoid division by ~0.
    cos_lat = max(math.cos(math.radians(lat)), 0.01)
    lng_delta = radius_km / (KM_PER_DEGREE_LAT * cos_lat)
    return BoundingBox(
        min_lat=lat - lat_delta,
        max_lat=lat + lat_delta,
        min_lng=lng - lng_delta,
        max_lng=lng + lng_delta,
    )
