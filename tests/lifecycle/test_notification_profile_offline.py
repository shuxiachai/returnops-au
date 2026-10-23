"""Offline AC09 checks for the closed CORE_MOCK notification profile.

These tests exercise formatting only, not producer proof, recipient authorization,
persistence, delivery, or HTTP access to the referenced evidence.
"""
import re

import pytest

from returnops_domain import notification_profile as profile


LABEL = "glabel_" + "a" * 64
OUTCOMES = ("RETURN_CREATED", "REJECTED", "MANUAL_HANDLED")


def test_closed_profile_inventory_and_category_dispositions():
    assert profile.PROFILES == {
        "RETURN_CREATED": "return-created-mock/v2",
        "REJECTED": "rejected-mock/v2",
        "MANUAL_HANDLED": "manual-handled-mock/v2",
    }
    assert profile.CHANNEL == "CORE_MOCK"
    assert profile.CATEGORIES == {
        "packaging": {"disposition": "NOT_APPLICABLE", "source": "FIXED_CORE_MOCK_BOUNDARY"},
        "drop_off": {"disposition": "NOT_APPLICABLE", "source": "FIXED_CORE_MOCK_BOUNDARY"},
        "responsibility": {"disposition": "UNKNOWN", "source": "NO_REVIEWED_REAL_WORLD_DETERMINATION"},
        "cost": {"disposition": "UNKNOWN", "source": "NO_REVIEWED_REAL_WORLD_DETERMINATION"},
        "next_step": {"disposition": "UNKNOWN", "source": "HUMAN_CONFIRMATION_REQUIRED"},
    }


@pytest.mark.parametrize("outcome", OUTCOMES)
def test_each_outcome_exposes_all_safe_categories(outcome):
    rendered = profile.render(outcome, label_evidence_id=LABEL if outcome == "RETURN_CREATED" else None)
    assert set(rendered) == {"message", "next_steps"}
    steps = " ".join(rendered["next_steps"]).lower()
    for term in ("packaging", "drop-off", "responsibility", "cost", "next step"):
        assert term in steps
    assert "not applicable" in steps
    assert "not yet determined" in steps
    assert "human confirmation" in steps
    assert "never post" in steps


def test_return_created_describes_mock_and_authorised_evidence_path():
    result = profile.render("RETURN_CREATED", label_evidence_id=LABEL)
    message = result["message"].lower()
    assert "simulated return" in message
    assert "not valid for postage" in message
    assert "not arranged a real shipment" in message
    assert "made a charge" in message
    assert f"/v1/evidence/{LABEL}/content" in result["next_steps"][0]
    assert "must not be used for postage" in result["next_steps"][0]


def test_rejection_and_manual_messages_preserve_scope_and_uncertainty():
    rejection = profile.render("REJECTED")["message"].lower()
    manual = profile.render("MANUAL_HANDLED")["message"].lower()
    assert "recorded a rejection" in rejection
    assert "does not determine your legal rights" in rejection
    assert "manual-handling outcome" in manual
    assert "uncertain" in manual
    assert "does not assert that it never happened" in manual
    assert "no shipment or payment is authorised" in manual


@pytest.mark.parametrize("outcome", ["", "return_created", "UNKNOWN", "SENT"])
def test_unknown_outcomes_fail_closed(outcome):
    with pytest.raises(ValueError):
        profile.render(outcome, label_evidence_id=LABEL)
    with pytest.raises(ValueError):
        profile.profile_hash(outcome)


@pytest.mark.parametrize("label", [None, "", "glabel_" + "a" * 63, "glabel_" + "a" * 65,
                                    "glabel_" + "A" * 64, "glabel_" + "g" * 64,
                                    "glabel_" + "a" * 64 + "\n", 123])
def test_return_requires_exact_certified_label_shape(label):
    with pytest.raises(ValueError):
        profile.render("RETURN_CREATED", label_evidence_id=label)


@pytest.mark.parametrize("outcome", ["REJECTED", "MANUAL_HANDLED"])
def test_non_return_outcomes_cannot_attach_a_label(outcome):
    with pytest.raises(ValueError):
        profile.render(outcome, label_evidence_id=LABEL)


@pytest.mark.parametrize("argument", ["message", "recipient", "profile", "next_steps"])
def test_caller_cannot_supply_profile_content_or_recipient(argument):
    with pytest.raises(TypeError):
        profile.render("REJECTED", **{argument: "caller controlled"})


def test_render_returns_fresh_steps_and_hashes_bind_profile_content(monkeypatch):
    first = profile.render("REJECTED")
    original_hash = profile.profile_hash("REJECTED")
    assert re.fullmatch(r"[0-9a-f]{64}", original_hash)
    assert original_hash == profile.profile_hash("REJECTED")
    assert len({profile.profile_hash(outcome) for outcome in OUTCOMES}) == 3
    first["next_steps"].append("caller mutation")
    assert "caller mutation" not in profile.render("REJECTED")["next_steps"]
    assert original_hash == profile.profile_hash("REJECTED")
    monkeypatch.setitem(profile.MESSAGES, "REJECTED", "changed content")
    assert original_hash != profile.profile_hash("REJECTED")
