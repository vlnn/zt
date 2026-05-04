# Literate style for example files

This is the convention for prose-driven Forth files in `examples/`.
It complements [`forth-style.md`](forth-style.md), which covers how
each *word* should look. This guide covers how a *file* should be
composed from already-good Forth: the prose that sits between word
definitions, and the section structure that prose imposes.

The thesis: Forth is read top-to-bottom, so the file should *teach
itself* on a single pass. That means motivation comes before
mechanism, and the file should be skimmable at the level of section
headers alone.

## The shape of a literate file

```
\ <top-of-file paragraph: what this file is, what role it plays>

<imports>


\ Section title
\ ─────────────
\ <paragraph motivating this section>

<word definitions>


\ Next section title
\ ──────────────────
\ <paragraph>

<word definitions>
...
```

Two blank lines before each section divider, one blank line after
the prose before the code. Sections are conceptual units, not
arbitrary chunks: a section is the unit you'd point at if asked
"what part of this file handles X?"

## The top-of-file overview

One paragraph, two to four sentences. Says what this file is
responsible for and what it isn't. If there's a non-obvious choice
that shapes the whole file (e.g. "items store rooms, not the
inverse"), name it here so the rest of the file makes sense.

```forth
\ The static world: items, directions, rooms, the corridors between them,
\ and where things start out.  Run-time mutable state — the player's
\ location and where each item is — lives here too, since every query
\ touches it.
```

Don't list the public words. The reader is about to see them.

## Section headers

Format: a `\ Title` line followed by a `\ ───…` line of em-dashes
roughly matching the title's width. Title is sentence case
(`Player and item state`), not Title Case, not all-lowercase. The
title names a *concept*, not a category — `Exits: bidirectional
connection` is better than `Exit helpers`, and both are better than
`connect-pair`.

When several sections share a theme, prefix with `Topic:`:

```
\ Exits: basics
\ Exits: bidirectional connection
\ Exits: clearing a room
\ Exits: the corridor table
\ Exits: assembly
```

That's the cue that you can read them in order to build up the
exit subsystem.

## The section paragraph

Two to five sentences, written as flowing prose. Things worth a
paragraph:

- **Design decisions**, especially ones whose inverse would also
  work. "Storing the location *on the item* (rather than items on
  rooms) makes 'where is X?' O(1) and makes 'X exists in two
  places' structurally impossible."
- **Non-obvious idioms**. "`fill` writes one byte at a time and
  exits are 16-bit cells. We want every byte to be 255, which is
  (-1 & 0xFF) and sign-extends back to -1."
- **Conventions a reader needs to know to read the next 30 lines**.
  "One row across these three parallel arrays describes one
  bidirectional corridor."
- **Why the ordering matters**. "Defined here, before the room
  records, so each record can capture the description's xt at
  compile time."
- **Why the obvious approach didn't work**. "The natural fit is
  `item-loc ['] copy-from-homes map-word`, but `map-word`'s xt sees
  `( v -- v' )` — the current value, not the index."

Things **not** worth a paragraph:

- **Restating a word's name in English.** "`opposite-dir` returns
  the opposite direction" earns no one anything.
- **Self-explanatory wrappers.** A section of one-liners like
  `in-room?` and `carrying?` may not need any prose at all — the
  section header is enough.
- **What a stack-effect comment already says.**

If a section has nothing worth a paragraph, **skip the paragraph**
and let the section header carry the structure. Forced prose is
worse than no prose.

## Forward references

The reader is going top-to-bottom, so it's fine — useful, even —
to mention words that don't exist yet:

> Each room is 4 cells of -1 (blocked exits, populated by
> `init-exits` at run time), followed by the xt of its description.

That tells the reader the `-1`s aren't permanent without making
them flip back to find out.

## Stack-effect comments

Keep them on every defined word, including the trivial ones. They
are types, not prose, and `forth-style.md` is clear about this.
Literate prose **does not replace** stack-effect comments — the
prose explains the *design*; the stack effect documents the
*interface*.

## Inline comments inside word bodies

Don't. Same rule as `forth-style.md`: if the body needs prose to be
readable, the body needs more factoring. The literate paragraphs
sit *between* word definitions, not inside them.

The one exception is a non-obvious magic constant:

```forth
: clear-exits    ( room -- )    .exits +  8 255 fill ;
```

The `255` is explained in the section paragraph — better than an
inline comment, because it answers the question once for everyone
who reads the file.

## Application-style files

Files that are complete applications rather than teaching examples
(zlm-tinychat, large parts of mined-out, the IM2 demos) get
**top-of-file overview only**: two or three paragraphs covering
what the program does, the high-level architecture, and any global
conventions. No per-section prose — the file is too long, and the
sections are too many, for paragraph-per-section to add value.

For those files, individual section headers without paragraphs are
still useful for navigation.

## What's out of scope

- Test files (`test_*.fs`, `test_*.py`). They're specifications,
  not examples. A short top-of-file comment is enough.
- `main.fs` files that are one or two lines. Nothing to say.
- Stdlib files (`stdlib/`, `src/zt/stdlib/`). Different doc
  obligations.

## The skim test

Before declaring a literate rewrite done, scroll through the file
reading **only the section headers**. Two questions:

1. Could a reader who knows the language but not this file build a
   mental map of what's in here from the headers alone?
2. Is each section's role distinct from its neighbours?

If the answer to either is no, the sections are wrong. Common
fixes: merge two redundant sections, split one that's doing two
jobs, or rename a section whose title doesn't actually describe
its contents.

## Per-rewrite checklist

Before staging a file:

- [ ] Top-of-file paragraph exists and frames the file's role.
- [ ] Section headers are concept names, not category labels.
- [ ] Every paragraph earns its place — no restating names, no
      filler. Removed if there's nothing to say.
- [ ] Forward references hint what's coming so the reader doesn't
      have to flip ahead.
- [ ] Stack-effect comments are on every `:` word (literate prose
      doesn't replace them).
- [ ] No inline comments inside word bodies.
- [ ] The skim test passes.
- [ ] All existing tests still pass.

## A small worked example

**Before** (no literate structure):

```forth
\ player movement
0 constant dir-n
1 constant dir-s
2 constant dir-e
3 constant dir-w

: opposite-dir  ( dir -- dir' )  1 xor ;

: connect-pair  ( a b dir -- )
    >r  2dup swap  r@           connect
    r>           opposite-dir   connect ;
```

**After**:

```forth
\ Directions
\ ──────────
\ A direction is a cell index into a room's .exits array, so we get
\ four slots per room.  The numbering is deliberate: dir-n/dir-s
\ share the low pair (0/1) and dir-e/dir-w the high pair (2/3).
\ Flipping bit 0 walks across each axis without a lookup table.

0 constant dir-n
1 constant dir-s
2 constant dir-e
3 constant dir-w

: opposite-dir   ( dir -- dir' )   1 xor ;


\ Exits: bidirectional connection
\ ───────────────────────────────
\ Adventure-game corridors should be walkable both ways: if the
\ kitchen's north exit goes to the hallway, the hallway's south
\ exit had better go back.  connect-pair wires both directions in
\ one call, using opposite-dir for the return trip.

: connect-pair   ( a b dir -- )
    >r  2dup swap  r@           connect
    r>           opposite-dir   connect ;
```

The "after" is longer, but a reader who's never seen this code
before now knows *why* `1 xor` works, *what* a direction is, and
*why* `connect-pair` calls `connect` twice — without reading any
word body.
