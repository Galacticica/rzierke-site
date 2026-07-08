"""
File: test_filters.py
Description: Unit tests for PieceFilter — free-text q plus instrument and
piece_type multi-select (OR semantics, conjoined=False).
"""

import pytest

from rzpercussion.filters import PieceFilter
from rzpercussion.models import Instrument, Piece, PieceType

pytestmark = pytest.mark.django_db


@pytest.fixture
def marimba():
    return Instrument.objects.create(name="Marimba")


@pytest.fixture
def snare():
    return Instrument.objects.create(name="Snare Drum")


@pytest.fixture
def solo_type():
    return PieceType.objects.create(name="Solo")


@pytest.fixture
def ensemble_type():
    return PieceType.objects.create(name="Ensemble")


@pytest.fixture
def pieces(marimba, snare, solo_type, ensemble_type):
    marimba_solo = Piece.objects.create(
        title="Marimba Spiritual", composer="Minoru Miki", piece_type=solo_type
    )
    marimba_solo.instrument.add(marimba)

    snare_solo = Piece.objects.create(
        title="Prim", composer="Askell Masson", piece_type=solo_type
    )
    snare_solo.instrument.add(snare)

    ensemble = Piece.objects.create(
        title="Ionisation", composer="Edgard Varese", piece_type=ensemble_type
    )
    ensemble.instrument.add(marimba, snare)

    untagged = Piece.objects.create(title="Untitled Sketch", composer="Anon")

    return {
        "marimba_solo": marimba_solo,
        "snare_solo": snare_solo,
        "ensemble": ensemble,
        "untagged": untagged,
    }


def _qs(data):
    return PieceFilter(data, queryset=Piece.objects.all()).qs


def test_no_params_returns_all(pieces):
    assert set(_qs({})) == set(pieces.values())


def test_q_matches_title(pieces):
    assert set(_qs({"q": "marimba spiritual"})) == {pieces["marimba_solo"]}


def test_q_matches_composer(pieces):
    assert set(_qs({"q": "varese"})) == {pieces["ensemble"]}


def test_q_blank_returns_all(pieces):
    assert set(_qs({"q": ""})) == set(pieces.values())


def test_q_no_match_returns_empty(pieces):
    assert list(_qs({"q": "zzz-no-such-piece"})) == []


def test_instrument_single_select(pieces, marimba):
    assert set(_qs({"instrument": [str(marimba.pk)]})) == {
        pieces["marimba_solo"],
        pieces["ensemble"],
    }


def test_instrument_multi_select_is_or(pieces, marimba, snare):
    # conjoined=False: pieces with EITHER instrument, each listed once.
    result = list(_qs({"instrument": [str(marimba.pk), str(snare.pk)]}))
    assert set(result) == {
        pieces["marimba_solo"],
        pieces["snare_solo"],
        pieces["ensemble"],
    }
    assert len(result) == 3  # ensemble has both instruments but appears once


def test_piece_type_single_select(pieces, solo_type):
    assert set(_qs({"piece_type": [str(solo_type.pk)]})) == {
        pieces["marimba_solo"],
        pieces["snare_solo"],
    }


def test_piece_type_multi_select_is_or(pieces, solo_type, ensemble_type):
    assert set(_qs({"piece_type": [str(solo_type.pk), str(ensemble_type.pk)]})) == {
        pieces["marimba_solo"],
        pieces["snare_solo"],
        pieces["ensemble"],
    }


def test_q_and_instrument_combined(pieces, marimba):
    result = _qs({"q": "ionisation", "instrument": [str(marimba.pk)]})
    assert set(result) == {pieces["ensemble"]}


def test_invalid_instrument_pk_is_rejected(pieces):
    # An unknown pk fails form validation; django-filter falls back to the
    # unfiltered queryset for a FilterSet whose form is invalid.
    filterset = PieceFilter({"instrument": ["999999"]}, queryset=Piece.objects.all())
    assert not filterset.form.is_valid()
