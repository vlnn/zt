import pytest

from transcribe_lilypond import (
    Event,
    SILENCE,
    parse_note_token,
    parse_voice,
    pitch_class,
    relative_midi,
    to_sixteenths,
    tokenize,
)


@pytest.mark.parametrize("name,expected", [
    ("c", 0), ("d", 2), ("e", 4), ("f", 5),
    ("g", 7), ("a", 9), ("b", 11),
])
def test_pitch_class_returns_semitone_offset(name, expected):
    assert pitch_class(name) == expected, (
        f"pitch_class({name!r}) should be {expected} semitones above C")


@pytest.mark.parametrize("dur,expected", [
    ("16", 1), ("8", 2), ("4", 4), ("2", 8),
    ("8.", 3), ("4.", 6), ("2.", 12),
])
def test_to_sixteenths_handles_basic_and_dotted(dur, expected):
    assert to_sixteenths(dur) == expected, (
        f"duration {dur!r} should be {expected} sixteenths")


def test_to_sixteenths_returns_none_for_missing_duration():
    assert to_sixteenths("") is None, (
        "empty duration should be None to mean 'inherit previous'")


@pytest.mark.parametrize("token,name,acc,octave_mod,dur,tied", [
    ("d16", "d", 0, 0, "16", False),
    ("bes", "b", -1, 0, "", False),
    ("cis,", "c", 1, -1, "", False),
    ("bes'", "b", -1, 1, "", False),
    ("g8.", "g", 0, 0, "8.", False),
    ("c!", "c", 0, 0, "", False),
    ("ees", "e", -1, 0, "", False),
    ("fis,8", "f", 1, -1, "8", False),
])
def test_parse_note_token_extracts_components(token, name, acc, octave_mod, dur, tied):
    note = parse_note_token(token)
    assert note.pitch == name, f"{token!r} pitch should be {name!r}"
    assert note.accidental == acc, f"{token!r} accidental should be {acc:+d}"
    assert note.octave_modifier == octave_mod, (
        f"{token!r} octave modifier should be {octave_mod:+d}")
    assert note.duration == dur, f"{token!r} duration should be {dur!r}"
    assert note.tied is tied, f"{token!r} tied flag should be {tied}"


def test_parse_note_token_recognises_tie():
    assert parse_note_token("bes~").tied is True, (
        "trailing ~ should mark the note as tied")


@pytest.mark.parametrize("prev_midi,pitch_class_v,octave_mod,expected", [
    (60, 2, 0, 62),
    (60, 11, 0, 59),
    (62, 4, 0, 64),
    (70, 1, 0, 73),
    (61, 10, 1, 70),
    (61, 10, -1, 46),
    (60, 6, 0, 66),
])
def test_relative_midi_picks_closest_then_applies_modifier(
    prev_midi, pitch_class_v, octave_mod, expected,
):
    got = relative_midi(prev_midi, pitch_class_v, octave_mod)
    assert got == expected, (
        f"relative_midi(prev={prev_midi}, pc={pitch_class_v}, mod={octave_mod}) "
        f"should be {expected}, got {got}")


def test_tokenize_strips_comments_and_directives():
    src = """
       d16[ e f g a bes] | % bar 1
       cis,[ bes' a g f e] |
    """
    tokens = list(tokenize(src))
    assert tokens == [
        "d16", "e", "f", "g", "a", "bes",
        "cis,", "bes'", "a", "g", "f", "e",
    ], "tokenizer should drop %comments, [], |, and emit only musical atoms"


def test_tokenize_keeps_rests_and_ties():
    src = "f,8 r bes ~ | bes[ a g] |"
    assert list(tokenize(src)) == ["f,8", "r", "bes~", "bes", "a", "g"], (
        "tokenizer should keep rests, attach trailing ~ to its note, and drop bar lines")


def test_parse_voice_handles_first_note_relative_to_anchor():
    events = parse_voice("d16 e f", anchor_midi=60)
    pitches = [e.midi for e in events if e is not SILENCE and e.midi is not None]
    assert pitches == [62, 64, 65], (
        "first note d in \\relative c' should be D4 (62), then ascending")


def test_parse_voice_inherits_duration_from_previous_note():
    events = parse_voice("d16 e f", anchor_midi=60)
    assert all(e.sixteenths == 1 for e in events), (
        "second and third notes should inherit 16th-note duration from first")


def test_parse_voice_handles_rest_and_tied_notes():
    events = parse_voice("f8 r bes~ bes", anchor_midi=60)
    durations = [e.sixteenths for e in events]
    assert durations == [2, 2, 2, 2], "all four events should be 8th-note (2 sixteenths) long"
    assert events[1].midi is None, "second event should be a rest (midi=None)"
    assert events[2].tied, "third event (bes~) should be marked tied"
    assert not events[3].tied, "fourth event should not be tied"


@pytest.mark.parametrize("midi,expected_period", [
    (60, 424),
    (62, 377),
    (69, 252),
    (74, 189),
    (76, 168),
])
def test_midi_to_ay_period_matches_known_pitches(midi, expected_period):
    from transcribe_lilypond import midi_to_ay_period
    got = midi_to_ay_period(midi)
    assert abs(got - expected_period) <= 2, (
        f"midi {midi} should yield AY period ~{expected_period}, got {got}")


def test_events_to_ticks_expands_durations():
    from transcribe_lilypond import events_to_ticks
    events = [Event(60, 2, False), Event(None, 4, False), Event(67, 1, False)]
    assert events_to_ticks(events) == [60, 60, None, None, None, None, 67], (
        "each event should occupy `sixteenths` consecutive tick slots")


def test_merge_voices_pairs_with_zero_for_silence():
    from transcribe_lilypond import merge_voices, midi_to_ay_period
    pairs = merge_voices([60, None, 67], [None, 48, 48])
    assert pairs[0] == (midi_to_ay_period(60), 0), "voice2 silence should be 0"
    assert pairs[1] == (0, midi_to_ay_period(48)), "voice1 silence should be 0"
    assert pairs[2] == (midi_to_ay_period(67), midi_to_ay_period(48))
