# Ctrl Alt Defeat — Game Rules

## About this document

The rules below are transcribed from the game's own printed rulebook,
**`instructions.pdf`**, with supporting detail from
**`facilitation_notes.pdf`**. Both are scans of the National Cyber
Force's Responsible Cyber Operations Game (© Crown copyright 2025). The card
reference at the end comes from the CSVs in `CardData/`.

**The rulebook is authoritative.** This implementation diverges from it in several
places, some of them significant. Those are listed in
[Where the implementation diverges](#where-the-implementation-diverges) rather than
being mixed into the rules themselves, so this document stays usable as a statement of how the game is actually meant to play.

Two notes on the source material:

- The OCR'd `.txt` files in `CardData/` read numeric card values very unreliably
  (Tesseract rendered "Responsible 1" variously as `ca`, `&`, `®`, `fo`). **Use the
  CSVs for card values, never the `.txt` files.**
- Neither PDF states a player count or the number of spaces on the board. Both are implementation choices here; see the divergences section.

---

## Aim of the game

Achieve your mission objective by conducting cyber operations using Intelligence,
Technology, Governance, and Cyber Intervention Cards, balancing effectiveness
against responsibility. **The winner is the first player to reach the centre of the
board.** The more responsible your cyber operations, the quicker you advance.

---

## Components

### Card categories

Action Cards come in four categories. An operation needs one of each.

| Category | On the cards | In this codebase | Cards |
| --- | --- | --- | --- |
| Intelligence | INTELLIGENCE | `Intelligence` | 20 |
| Technology | TECHNOLOGY | `Technology` | 18 |
| Governance | GOVERNANCE | `Governance` | 20 |
| Cyber Intervention | CYBER INTERVENTION | `Cybersecurity` | 19 |
| Glitch | GLITCH | `Glitch` | 12 |

The fourth category is **Cyber Intervention** on the physical cards and in
`CardData/actionCards.csv`, but was renamed **Cybersecurity** when the data was
converted to `data/full_action_cards.json`. The code, the proto definitions, and the
client UI all use "Cybersecurity". They mean the same category.

Alongside the 89 Action Cards (including Glitches) there are 24 Objective Cards.
The game pack also ships blank Action and Objective cards for making your own
expansion packs.

### The Cache

The **Cache** is the shared discard pile. Played and discarded cards go face up on
it, and when the Action Card pile runs out the Cache is shuffled and placed face
down to form a new one.

### Card values

Every Action Card and Objective Card carries two numbers:

- **Effective** — how much the card advances the operation. Drives movement.
- **Responsible** — how lawful and well-governed the operation is. Drives whether
  the operation succeeds at all.

The two trade off by design. Cyber Intervention cards are effective but
irresponsible; Governance cards are responsible but rarely effective.

Action Cards run Effective −2 to +3 and Responsible −2 to +2. Objective Cards run
Effective +2 to +6 and Responsible 0 to +2.

---

## Set up

1. Remove the blank Objective and Action Cards if you are not using them.
2. Shuffle the Objective and Action Cards, but keep the decks separate.
3. Deal each player **two Objective Cards** and **four Action Cards**.
4. Place the Objective and Action Card piles next to the board.
5. Roll a die to decide who goes first — highest wins.
6. Play rotates clockwise around the board.

---

## Objective Cards

To move around the board, players conduct cyber operations by fulfilling the tasks
on their Objective Cards. **Players may hold a maximum of two Objective Cards.**

## Action Cards

Action Cards are Intelligence, Technology, Governance and Cyber Interventions — the
elements needed to conduct an operation and complete the mission on your Objective
Card. **Players may hold a maximum of six Action Cards at the end of each turn.**

## Glitch Cards

Glitch Cards can have a positive or negative effect. **If a player draws a Glitch
Card it must be played immediately at the start of their turn.** If playing a Glitch
Card draws further Glitch Cards, those must be played too, until no Glitch Cards
remain in hand. Played and discarded Glitch Cards go face up on the Cache.

There are three effects:

| Effect | Cards | What happens |
| --- | --- | --- |
| **Draw** | 5 | Draw 2 more Action Cards immediately. |
| **Discard** | 5 | Discard 1 card, sometimes restricted to a named category. |
| **Skip operation** | 2 | You cannot complete an operation this turn. |

---

## On your turn

### Building your operation

1. **Draw two Action Cards** from the deck, or take the top card from the Cache if
   it is not a Glitch Card. If the Action Card pile runs out, shuffle the Cache and
   place the cards face down to form a new Action Card pile.
2. **Immediately play any Glitch Cards** in your hand until you have none remaining.
   Place any played or discarded cards face up on the Cache.
3. **Attempt to build your operation** by combining an Objective Card with one of
   each type of Action Card (Intelligence, Technology, Governance and Cyber
   Intervention). You must have one of each type to complete an operation.
4. If you can build a complete operation, check that you are happy with the
   responsibility and effectiveness scores before choosing to play it. **You may
   pass your turn** if you cannot, or do not wish to, play an operation.
5. **Discard** your choice of Action Cards face up on the Cache to keep a maximum of
   six in your hand.

Note that step 1 is not optional: drawing begins every turn, whether or not you go
on to play an operation.

### Playing an operation

1. Place the cards on the corresponding locations on the board. Describe the
   operation and explain your choices to the other players.
2. Determine the operation's success and score — see [Scoring](#scoring).
3. **If playing to win the game:** if your successful operation would take you over
   the finishing line, it must have a responsibility score of **3 or more**.
4. If your operation succeeds, move your counter forwards by the operation's
   effectiveness score. If its responsibility score was **4 or higher**, move
   forwards **one extra place and draw two Action Cards**.
5. If your operation fails, your counter remains in its current position.
6. Place any used Action Cards face up on the Cache, and the Objective Card at the
   bottom of the Objective Cards' deck.
7. Draw a new Objective Card to keep two in your hand.

The rulebook states the responsibility-3 requirement in step 3 but does not say what
becomes of an under-responsible operation that would otherwise have crossed the
line. This implementation reads it as a ceiling rather than a wasted turn: the
operation still succeeds and the player still advances, but stops one space short of
the centre. Reading it instead as "the operation fails outright" would be equally
consistent with the text.

---

## Scoring

Once you are ready to conduct an operation, determine its outcome by:

1. **Adding up the responsibility scores of all the cards in your operation,
   including the Objective Card.**
2. If the responsibility score is **4 or higher**, your operation succeeds.
3. If the responsibility score is **1, 2, or 3**, roll a die:

   | Die roll | Result |
   | --- | --- |
   | 1–2 | Fail |
   | 3–6 | Success |

4. If the responsibility score is **0 or less**, roll a die:

   | Die roll | Result |
   | --- | --- |
   | 1–2 | Player goes offline and must miss a turn |
   | 3–5 | Fail |
   | 6 | Success |

5. If your operation fails, it scores 0 for effectiveness.
6. If your operation succeeds, **add up the effectiveness scores of all the cards in
   your operation, including the Objective Card**, to give the operation's total
   effectiveness score.

---

## Advanced rules — the Coalition of Allies

An optional variant for more realism, teamwork and competition. The base rules are
unchanged, with these additions.

### Personalities

- One player (or the facilitator) is the **Adversary**.
- All other players form the **Coalition of Allies**.

### Offensive operations

A player may target any other player when conducting an operation. Responsibility is
calculated as usual to determine success or failure. If successful, **the target
moves their counter backwards** by the effectiveness score on the operation's
Objective Card.

### The Adversary

An irresponsible cyber actor who seeks to use cyber capabilities to cause harm.

1. The Adversary **ignores responsibility scores**. Success is determined by a die
   roll instead:

   | Die roll | Result |
   | --- | --- |
   | 1 | Go offline for one turn, or discard two Action Cards |
   | 2–4 | Partial success: score half the operation's effectiveness, rounded up |
   | 5–6 | Complete success: score full effectiveness |

2. An Adversary operation must always include a **Cyber Intervention and a
   Technology Card**, but Governance and Intelligence Cards are optional.

### The Coalition of Allies

Allies follow the base rules and may also collaborate:

1. They may show cards to each other (partial or full hands).
2. They may ask for one Action Card — **but not a Governance Card** — from an Ally
   to complete an operation.
3. They may swap one Action Card — **but not a Governance Card** — per turn with an
   Ally.

Governance Cards are excluded because the NCF would not ask a partner to undertake
activities that would be illegal for it to undertake, or that lie outside UK policy
boundaries; cyber operations must always be conducted within an organisation's own
governance structure.

### Winning the advanced game

The winner is still the first player to reach the centre of the board. The Allies
may wish to win individually, but also to collaborate to stop the Adversary. **A
final Ally operation to reach the centre must have a responsibility score of 3 or
more.**

---

## Where the implementation diverges

Differences between the rulebook above and the code in `src/`. Listed most
significant first.

Each entry says whether it is being worked on. "Accepted" means the difference is a
deliberate choice rather than an oversight, and closing it is not currently planned.

Two earlier divergences have since been fixed and are no longer listed: the
Objective Card's values were excluded from both scoring totals, and the
responsibility-3 floor for crossing the finishing line was missing. `Operation` now
seeds both totals from the objective, and `Game.MIN_RESPONSIBILITY_TO_FINISH`
enforces the floor by holding an under-responsible player one space short of the
centre.

### 1. Drawing is optional rather than the mandatory start of every turn

*Accepted, not currently planned.*

In the rulebook, every turn begins with step 1: draw two Action Cards. Only then do
you attempt an operation. The implementation instead offers Play, Draw, Discard and
Skip as four alternative turn actions, so a player can play an operation without
ever drawing, and can draw repeatedly without ending their turn.

### 2. No option to take the top card from the Cache

*Accepted, not planned.*

Step 1 of every turn allows taking the top Cache card instead of drawing two, as
long as it isn't a Glitch Card. The implementation only ever draws from the deck.
The rule mainly exists to keep a physical game moving when the deck runs low;
`Game._refill_if_empty` reshuffles the discard pile automatically, so the deck never
runs out and the option has nothing to solve here.

### 3. The objective deck is 15 cards instead of 24

*Known; fix deferred.*

`CardData/objectiveCards.csv` gives 9 of its 15 rows a count of 2, for a 24-card
deck. But that count column is unlabelled — the header row ends in two empty field
names, and the count lands inconsistently in the 5th or 6th column. When the CSV was
converted to `data/full_objective_cards.json` those columns became keys named `""`
and `__1`, and no `count` key was produced. `Game._copy_count()` looks for `count`,
finds nothing, and loads one copy of everything.

With 6 players taking 2 each at setup, only 3 Objective Cards would remain in the
deck. The action deck is unaffected — `actionCards.csv` has a properly named `Count`
column, and all 89 action cards load correctly.

### 4. The advanced variant is not implemented

*Accepted, not currently planned.*

No Adversary, no Coalition of Allies, no offensive operations, no card sharing. The
vestigial `role='ally'` parameter on `Player` — whose docstring mentions
`"adversary"` and `"agent"` — is the only trace of it, and nothing reads it.

### 5. Glitch Cards are withheld from the opening deal

*Accepted — a deliberate reading of an ambiguous rule.*

`Game.setup_game` pulls Glitch Cards out before dealing and shuffles them back in
afterwards, so no player can start with one. The rulebook says only to shuffle and
deal. It does say a Glitch Card is played "immediately at the start of their turn"
when *drawn*, which leaves dealt Glitches genuinely ambiguous, so this is a
reasonable reading rather than a clear error — but it is an added rule.

### 6. Smaller differences

- **Board shape.** The rulebook describes a spiral won by reaching the centre. The
  implementation uses a linear track of 20 spaces (0–19), won at space 19. Neither
  PDF states a space count.
- **Player count.** The implementation requires 3–6 players. Neither PDF states any
  limit.
- **First player.** The rulebook rolls a die, highest first, then play rotates
  clockwise. The implementation shuffles turn order randomly. Same effect.
- **Hand limit timing.** The rulebook makes discarding to six an explicit final step
  of every turn. The implementation checks the limit only after cards are drawn.
- **Glitch chain guard.** `Game._MAX_GLITCH_CHAIN = 50` caps glitch chaining to
  protect against a pathological all-Glitch deck. No such limit exists in the rules.

---

## Card reference

Values are **Effective** and **Responsible**; **№** is how many copies are in the
deck. Names are reproduced verbatim from `CardData/`, including the typos in the
source data (`Technical Reconnaisssance`, `Socail Media Botnet`, `Com0romise`,
`Counter Hostle Malware`, and others) — the code matches cards by these exact
strings.

### Objective Cards — 24 cards

| Card | Effective | Responsible | № |
| --- | --- | --- | --- |
| Counter Disinformation | 2 | 1 | 2 |
| Counter Hostle Malware | 3 | 1 | 2 |
| Disrupt a Terrorist Group | 4 | 2 | 2 |
| Disrupt Online Criminals | 3 | 1 | 2 |
| Disrupt State Threats | 5 | 0 | 2 |
| Expose Illegal Activity | 3 | 0 | 2 |
| Expose State Threats | 2 | 1 | 2 |
| Influence Behaviours of Hostile Actors | 3 | 0 | 2 |
| Prevent Cyber Attacks | 2 | 2 | 2 |
| Protect Military Operations | 5 | 0 | 2 |
| Support Law Enforcement | 4 | 1 | 2 |
| Support to Military Operations | 6 | 0 | 2 |

### Intelligence — 20 cards

| Card | Effective | Responsible | № |
| --- | --- | --- | --- |
| Agent Recruitment | 1 | 2 | 2 |
| Communications Intercept | 2 | 0 | 3 |
| Open Source Scanning | 1 | 1 | 3 |
| Partners | 1 | 2 | 3 |
| Public Records | 0 | 1 | 2 |
| Signals Intelligence | 2 | 1 | 4 |
| Technical Reconnaisssance | 2 | 1 | 3 |

### Technology — 18 cards

| Card | Effective | Responsible | № |
| --- | --- | --- | --- |
| Access to Data | 1 | 1 | 1 |
| Backdoor | 2 | 0 | 1 |
| Clandestine Technology | 3 | 1 | 1 |
| Code Injection | 2 | 1 | 1 |
| Covert Influence | 1 | 1 | 1 |
| Credential Theft | 3 | 1 | 1 |
| Default Passwords | 0 | 0 | 1 |
| Digital Communications Systems Disruption | 2 | 1 | 1 |
| Disrupting Communication Devices | 1 | 0 | 1 |
| Email Spoofing | 0 | 0 | 1 |
| Hardware Supply Chain Attack | 2 | 1 | 1 |
| Internet of Things Device Attack | 1 | 1 | 1 |
| Kill Switch | 3 | 1 | 1 |
| Manipulaltion of Data | 1 | 1 | 1 |
| Online Influence | 1 | 1 | 1 |
| Reverse Engineering | 3 | 1 | 1 |
| Technology Degredation | 2 | 1 | 1 |
| Zero Day | 3 | 0 | 1 |

### Governance — 20 cards

| Card | Effective | Responsible | № |
| --- | --- | --- | --- |
| Cautious | −2 | 1 | 2 |
| Independent Oversight | 0 | 1 | 2 |
| Lack of Oversight | 0 | −2 | 2 |
| Learning Culture | 1 | 1 | 1 |
| Legal Authority | 0 | 2 | 2 |
| Ministerial Approval | 0 | 1 | 2 |
| National Secuity Council | 0 | 1 | 1 |
| Parliamentary Scrutiny | 0 | 1 | 1 |
| Questionable Values and Ethics | 0 | −2 | 3 |
| Risk Management | 1 | 1 | 1 |
| Values and Ethics | 1 | 1 | 3 |

### Cyber Intervention — 19 cards

| Card | Effective | Responsible | № |
| --- | --- | --- | --- |
| CNI Attack | 2 | −2 | 2 |
| CNI Pre-positioning | 1 | 0 | 1 |
| counter Propaganda | 1 | 1 | 1 |
| data Encruption | 1 | 0 | 1 |
| Data Manipulation | 1 | −1 | 1 |
| Denial of Service | 1 | −1 | 1 |
| Industrial Attack | 2 | −2 | 2 |
| Information Release *(to the internet)* | 1 | −1 | 1 |
| Information Release *(to journalists)* | 2 | 0 | 1 |
| Intelligence Release | 1 | −1 | 2 |
| Network Attack | 2 | −1 | 3 |
| Socail Media Botnet | 2 | −1 | 2 |
| Software Supply Chain Attack | 2 | −1 | 1 |

Two distinct cards share the name **Information Release**, distinguished only by
their descriptions and values.

### Glitch Cards — 12 cards

| Card | Effect | № |
| --- | --- | --- |
| Approval Delay | You cannot complete an operation this turn | 1 |
| Budget Increase | Draw 2 Action Cards | 1 |
| Com0romise | Discard 1 Technology Card | 1 |
| Disclose a Zero Day Exploit | Discard 1 Technology card | 1 |
| International Agreement Published | Draw 2 Action Cards | 2 |
| Keep a Zero Day Exploit | Draw 2 Action Cards | 1 |
| Legislative Change | Discard 1 Governance Card | 1 |
| Operation Review | You cannot complete an operation this turn | 1 |
| Resource Reshuffle *(in your favour)* | Draw 2 Action Cards | 1 |
| Resource Reshuffle *(crisis event)* | Discard 1 Action Card | 1 |
| Technology Fails | Discard 1 Technology card | 1 |

Two distinct cards share the name **Resource Reshuffle** with opposite effects — one
draws, one discards.
