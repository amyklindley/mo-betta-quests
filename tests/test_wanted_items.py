"""wanted_items(): every 'N <things>' / 'collect a <thing>' / 'X from the Y' parse."""
import mnm_quests as mq


def words(items, i):
    return items[i][1]


def test_counted_plural_items():
    items = mq.wanted_items("Bring me five of their bone chips and I will pay you well.")
    assert len(items) == 1
    count, nouns, phrase, scope = items[0]
    assert count == 5
    assert nouns == ["bone", "chip"]
    assert phrase == "bone chips"
    assert scope is None


def test_digit_quantities():
    items = mq.wanted_items("I need 8 cracked fangs from the temple beasts.")
    assert items[0][0] == 8
    assert items[0][1] == ["cracked", "fang"]


def test_irregular_plurals_singularized():
    items = mq.wanted_items("Bring me three teeth from the elder wolves.")
    assert items[0][1] == ["tooth"]


def test_generic_unit_defers_to_the_noun_after_of():
    items = mq.wanted_items("Bring me six portions of either meat for the stew.")
    assert items[0][0] == 6
    assert items[0][1] == ["meat"]
    assert items[0][2] == "portions of meat"


def test_singular_head_noun_with_plural_count_skipped():
    # "two fruit" -> head noun is singular, not a counted request.
    assert mq.wanted_items("Pick two fruit from the orchard for the festival.") == []


def test_single_item_and_continuation_list():
    items = mq.wanted_items("Collect a fire beetle eye, a rat tail, and a snake fang for the alchemist.")
    assert [(i[0], i[1]) for i in items] == [
        (1, ["fire", "beetle", "eye"]),
        (1, ["rat", "tail"]),
        (1, ["snake", "fang"]),
    ]


def test_ellipsis_list_with_sources():
    text = ("Collect the following supplies for the ritual:"
            "...a natural light source, butchered from a proximal creature..."
            "...a venom gland, carefully removed from a snake..."
            "...three meaty legs, torn from a beetle...")
    items = mq.wanted_items(text)
    assert len(items) == 3
    # The numbered entry is claimed by QTY_RE first; creature sources are notable.
    assert items[0] == (3, ["meaty", "leg"], "meaty legs", None)
    # "a proximal creature" is a vague source -> no creature prefix.
    assert items[1] == (1, ["natural", "light", "source"], "natural light source", None)
    assert items[2][0] == 1
    assert items[2][1] == ["snake", "venom", "gland"]
    assert "(from snake)" in items[2][2]


def test_from_lists_need_two_or_more():
    text = "Meat from the rats, eggs from the snakes, and legs from the beetles."
    items = mq.wanted_items(text)
    assert [(i[1], i[2]) for i in items] == [
        (["rat", "meat"], "meat from the rats"),
        (["snake", "egg"], "eggs from the snakes"),
        (["beetle", "leg"], "legs from the beetles"),
    ]


def test_single_from_is_not_an_item_list():
    assert mq.wanted_items("The stew needs meat from the boar and nothing else.") == []


def test_participles_are_not_from_items():
    assert mq.wanted_items("The meat will be butchered from the beast tomorrow.") == []


def test_of_list_creature_parts():
    text = "I need the eye of a bat, a fire beetle, and a crypt scarab for the ward."
    items = mq.wanted_items(text)
    assert [(i[0], i[1]) for i in items] == [
        (1, ["bat", "eye"]),
        (1, ["fire", "beetle", "eye"]),
        (1, ["crypt", "scarab", "eye"]),
    ]


def test_of_list_requires_a_body_part():
    # "out of the ordinary" must not parse as an item list.
    assert mq.wanted_items("Step out of the ordinary and you will be rewarded.") == []


def test_quantity_and_single_item_coexist():
    items = mq.wanted_items("Collect six beetle legs and bring me a rat tail for proof.")
    assert [(i[0], i[1]) for i in items] == [
        (6, ["beetle", "leg"]),
        (1, ["rat", "tail"]),
    ]


def test_stop_nouns_rejected():
    assert mq.wanted_items("Two pieces of advice for the road, friend.") == []
    assert mq.wanted_items("Take five steps toward the gate and wait.") == []


def test_from_items_without_numbers_have_zero_count():
    items = mq.wanted_items("Wings from the great bats, and legs from the cave crickets.")
    assert [(i[0], i[1]) for i in items] == [
        (0, ["bat", "wing"]),
        (0, ["cricket", "leg"]),
    ]


def test_vague_source_scope_keeps_npc_wording():
    items = mq.wanted_items("Meat from the four-legged ones, eggs from the snakes, and legs from the beetles.")
    vague = [i for i in items if i[3] is not None]
    assert len(vague) == 1
    assert vague[0][2] == "meat from the four-legged ones"
    assert vague[0][3] == {"meat"}


def test_single_after_verb_keeps_three_word_noun():
    items = mq.wanted_items("Go and find a dune scarab shell for the shaman.")
    assert (items[0][0], items[0][1]) == (1, ["dune", "scarab", "shell"])