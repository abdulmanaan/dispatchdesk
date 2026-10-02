"""Unit tests for distance maths and candidate ranking (no database)."""

import uuid

import pytest

from app.services.dispatch import Candidate, rank_candidates, score
from app.services.geo import bounding_box, haversine_km

LIBERTY_MARKET = (31.5104, 74.3416)
MINAR_E_PAKISTAN = (31.5925, 74.3095)


def test_haversine_zero_distance() -> None:
    assert haversine_km(*LIBERTY_MARKET, *LIBERTY_MARKET) == 0


def test_haversine_known_distance() -> None:
    # London -> Paris is about 343.5 km as the crow flies.
    assert haversine_km(51.5074, -0.1278, 48.8566, 2.3522) == pytest.approx(343.5, abs=1)


def test_haversine_within_lahore() -> None:
    # Liberty Market (Gulberg) -> Minar-e-Pakistan is roughly 9.6 km in a straight line.
    distance = haversine_km(*LIBERTY_MARKET, *MINAR_E_PAKISTAN)
    assert distance == pytest.approx(9.6, abs=0.3)
    assert distance == haversine_km(*MINAR_E_PAKISTAN, *LIBERTY_MARKET)


@pytest.mark.parametrize("radius", [1, 5, 15])
def test_bounding_box_contains_circle(radius: float) -> None:
    lat, lng = LIBERTY_MARKET
    box = bounding_box(lat, lng, radius)

    # Points exactly `radius` km north/south/east/west must be inside the box.
    assert haversine_km(lat, lng, box.max_lat, lng) >= radius * 0.999
    assert haversine_km(lat, lng, box.min_lat, lng) >= radius * 0.999
    assert haversine_km(lat, lng, lat, box.max_lng) >= radius * 0.999
    assert haversine_km(lat, lng, lat, box.min_lng) >= radius * 0.999


def candidate(distance: float, deliveries: int = 0) -> Candidate:
    return Candidate(driver_id=uuid.uuid4(), distance_km=distance, recent_deliveries=deliveries)


def test_nearest_driver_wins_with_equal_workload() -> None:
    near, far = candidate(1.2), candidate(3.4)

    assert rank_candidates([far, near], workload_penalty_km=1.0)[0] == near


def test_workload_penalty_can_favour_a_farther_driver() -> None:
    busy_near = candidate(1.0, deliveries=3)  # score 1.0 + 3 * 1.0 = 4.0
    idle_far = candidate(2.5, deliveries=0)  # score 2.5

    assert score(busy_near, 1.0) == 4.0
    assert rank_candidates([busy_near, idle_far], workload_penalty_km=1.0)[0] == idle_far
    # With the penalty disabled, pure distance decides.
    assert rank_candidates([busy_near, idle_far], workload_penalty_km=0)[0] == busy_near


def test_equal_score_prefers_nearer_driver() -> None:
    a = candidate(2.0, deliveries=1)  # 3.0
    b = candidate(3.0, deliveries=0)  # 3.0

    assert rank_candidates([b, a], workload_penalty_km=1.0)[0] == a
