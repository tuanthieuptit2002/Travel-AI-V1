from app.providers.mock import MockPlacesProvider
from app.providers.models import PlaceCategory, PlaceDetails, PlaceSearchRequest, PlaceSearchResult


def test_search_places_returns_normalized_results_for_da_nang_beaches() -> None:
    provider = MockPlacesProvider()

    results = provider.search_places(PlaceSearchRequest(query="beach", destination="Da Nang"))

    assert len(results) >= 1
    assert isinstance(results[0], PlaceSearchResult)
    assert any(result.name == "My Khe Beach" for result in results)
    assert all(result.destination == "Da Nang" for result in results)
    assert any(result.category is PlaceCategory.ATTRACTION for result in results)


def test_search_places_supports_destination_alias_and_categories() -> None:
    provider = MockPlacesProvider()

    results = provider.search_places(PlaceSearchRequest(destination="Saigon", category=PlaceCategory.LANDMARK))

    assert [result.name for result in results] == ["Saigon Central Post Office"]


def test_get_place_details_returns_typed_data_or_none() -> None:
    provider = MockPlacesProvider()

    details = provider.get_place_details("vn-hoian-banh-mi-phuong")

    assert isinstance(details, PlaceDetails)
    assert details is not None
    assert details.price_level == "low"
    assert provider.get_place_details("missing-place") is None
