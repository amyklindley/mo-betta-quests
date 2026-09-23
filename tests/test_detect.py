"""is_task(): what counts as an NPC instruction."""
import pytest

import mnm_quests as mq


def test_short_sentences_never_tasks():
    assert not mq.is_task("Bring me gold.")
    assert not mq.is_task("Yes.")


def test_done_cues_never_tasks():
    assert not mq.is_task("Thank you for bringing the bag, adventurer. I will not forget this kindness.")
    assert not mq.is_task("Excellent work on the cellar, you have done well indeed.")


@pytest.mark.parametrize(
    "s",
    [
        "Could you please bring me the supply crate from the depot?",
        "I need you to take this tunic to Old Man Sedgewick at the farm.",
        "We have a task for you, traveler, and it pays well.",
        "Your first task is to clear the tomb of these foul creatures.",
        "You are hereby ordered to report to the quartermaster at dawn.",
        "Would you be so kind as to fetch my ledger from the inn?",
        "All we ask is that you speak with the herbalist in the west wing.",
    ],
)
def test_explicit_requests_count(s):
    assert mq.is_task(s)


@pytest.mark.parametrize(
    "s",
    [
        "Well met, traveler. Take care out there on the road.",
        "Greetings, friend. How may I be of service to you today?",
        "I suppose the old mill has seen better days, has it not?",
        "Please, take a seat by the fire and warm your bones.",
        "You look tired from the journey, traveler.",
        "Give me a moment while I finish this ledger.",
    ],
)
def test_noise_is_ignored(s):
    assert not mq.is_task(s)


@pytest.mark.parametrize(
    "s",
    [
        "Bring me five of their bone chips and I will pay you well for them.",
        "Kill the rats in the cellar and bring me their tails for proof.",
        "The wolves have grown bold - thin out their pack before the moon rises.",
        "Gather a dozen nightshade leaves from the shaded grove at dusk.",
        "Speak with the harbormaster about the missing supply shipment.",
        "Take this coin to the smith and have him forge a new key.",
        "Now, go see the quartermaster about the missing supplies.",
        "Once you are ready, head east past the fallen ruins to the shrine.",
    ],
)
def test_task_wording_and_imperatives_count(s):
    assert mq.is_task(s)


@pytest.mark.parametrize(
    "s",
    [
        "Have you seen the old smith lately?",
        "Is the shrine still guarded by those stone constructs?",
        "The miller's daughter told me the flood took the west road.",
    ],
)
def test_questions_without_request_are_ignored(s):
    assert not mq.is_task(s)


def test_obligation_wording_counts():
    assert mq.is_task("You will need to clear the tomb before the moon rises over the dunes.")
    assert mq.is_task("Be sure to return the key to me once you have taken the ledger from the vault.")
    assert mq.is_task("Remember to bring the payment back to the guild hall.")


def test_min_len_applies_before_other_checks():
    assert not mq.is_task("Go east.")  # imperative but far below MIN_LEN


def test_request_with_reward_language_is_still_a_task():
    # "as promised" is a DONE cue, but it must not turn a fetch request into a turn-in.
    s = "Bring me three of their honey drops and I will bake you a cake as promised."
    assert mq.is_task(s)
    s2 = "Take this coin to the smith, and I will reward you as promised."
    assert mq.is_task(s2)