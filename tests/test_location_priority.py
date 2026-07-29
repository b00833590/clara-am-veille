from src.location_priority import location_priority


def test_paris_is_priority_1():
    assert location_priority("Paris, France") == 1


def test_ile_de_france_suburb_is_priority_1():
    assert location_priority("La Défense, France") == 1
    assert location_priority("Suresnes") == 1
    assert location_priority("Puteaux, Île-de-France") == 1


def test_london_is_priority_2():
    assert location_priority("London, United Kingdom") == 2
    assert location_priority("Londres") == 2


def test_other_major_european_financial_centre_is_priority_3():
    assert location_priority("Frankfurt, Germany") == 3
    assert location_priority("Luxembourg") == 3
    assert location_priority("Zurich, Switzerland") == 3
    assert location_priority("Milan, Italy") == 3


def test_rest_of_world_is_priority_4():
    assert location_priority("Hong Kong") == 4
    assert location_priority("New York, NY") == 4
    assert location_priority("Singapore") == 4


def test_unknown_or_missing_location_is_priority_4():
    assert location_priority(None) == 4
    assert location_priority("") == 4


def test_matching_is_case_insensitive():
    assert location_priority("PARIS") == 1
    assert location_priority("london") == 2
