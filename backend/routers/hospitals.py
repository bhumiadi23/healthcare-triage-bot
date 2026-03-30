"""
GET /hospitals/nearby  — Find nearby hospitals using Nominatim (OpenStreetMap, no API key)
GET /hospitals/route   — Get directions URL to nearest hospital
"""
import asyncio
import requests
import math
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def _haversine(lat1, lng1, lat2, lng2) -> float:
    """Distance in km between two coordinates."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def _find_hospitals(lat: float, lng: float, urgency: str) -> dict:
    radius_km = 3 if urgency in ("CRITICAL", "HIGH") else 10
    delta = radius_km / 111.0  # 1 degree ≈ 111 km

    params = {
        "q":              "hospital",
        "format":         "json",
        "addressdetails": 1,
        "limit":          10,
        "viewbox":        f"{lng-delta},{lat+delta},{lng+delta},{lat-delta}",
        "bounded":        0,  # not strictly bounded so we get more results
    }
    headers = {"User-Agent": "healthcare-triage-bot/1.0 (educational project)"}
    resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    results = resp.json()

    hospitals = []
    for place in results:
        h_lat = float(place.get("lat", 0))
        h_lng = float(place.get("lon", 0))
        dist = _haversine(lat, lng, h_lat, h_lng)
        addr = place.get("address", {})
        hospitals.append({
            "name":           place.get("display_name", "").split(",")[0],
            "address":        ", ".join(filter(None, [
                addr.get("road"),
                addr.get("suburb"),
                addr.get("city") or addr.get("town"),
                addr.get("state"),
            ])),
            "lat":            h_lat,
            "lng":            h_lng,
            "distance_km":    round(dist, 2),
            "maps_url":       f"https://www.openstreetmap.org/?mlat={h_lat}&mlon={h_lng}&zoom=16",
            "directions_url": f"https://www.google.com/maps/dir/{lat},{lng}/{h_lat},{h_lng}",
        })

    hospitals.sort(key=lambda x: x["distance_km"])
    return {"hospitals": hospitals[:5], "total": len(hospitals[:5])}


@router.get("/nearby", summary="Find nearby hospitals (OpenStreetMap, no API key)")
async def nearby_hospitals(
    lat:     float = Query(..., description="Patient latitude"),
    lng:     float = Query(..., description="Patient longitude"),
    urgency: str   = Query("HIGH", description="Urgency level: CRITICAL, HIGH, MEDIUM, LOW"),
):
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, _find_hospitals, lat, lng, urgency)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Map service error: {str(e)}")

    return {
        "urgency":  urgency,
        "location": {"lat": lat, "lng": lng},
        "radius_km": 3 if urgency in ("CRITICAL", "HIGH") else 10,
        "source":   "OpenStreetMap / Nominatim",
        **result,
    }


@router.get("/route", summary="Get directions URL to a hospital")
async def get_route(
    origin_lat: float = Query(...),
    origin_lng: float = Query(...),
    dest_lat:   float = Query(...),
    dest_lng:   float = Query(...),
):
    return {
        "google_maps": f"https://www.google.com/maps/dir/{origin_lat},{origin_lng}/{dest_lat},{dest_lng}",
        "osm":         f"https://www.openstreetmap.org/directions?from={origin_lat},{origin_lng}&to={dest_lat},{dest_lng}",
        "distance_km": round(_haversine(origin_lat, origin_lng, dest_lat, dest_lng), 2),
    }
