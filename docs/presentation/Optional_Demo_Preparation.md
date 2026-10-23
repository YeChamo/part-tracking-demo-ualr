# Optional demo preparation

Presentation documents only. Neither insert is enabled in the main talk.
The current deck has 17 slides. The demonstration is slide 12 at 0:16–0:36,
close by 0:40, show the homepage QR on slide 16, and begin final-slide activity at 0:41.
Use the [main speaker script](Speaker_Script.md) and [main cues](Phone_Cue_Cards.md)
unless an optional insert is deliberately selected.

## Sentiment

Use the separately prepared local teaching experiment. Its controls are Try 5
negative, Analyze messages, Clear session, and Why this result?. Checked scores:
five negative comments -58; five positive comments +56; The product is good.
+40; The product is not good. -40. Clear between the last two to show individual
scores. Keeping both averages to zero. Unmatched wording is unclassified.
This teaching copy uses English word rules. The broader project described on
slide 9 uses VADER with domain vocabulary. The stage script distinguishes them.

## REMI / Little Chef preparation and prompts

Software, models, credentials, private documents, and recordings are not included.
Complete the following in the actual Little Chef app before selecting this insert.

```text
OPTIONAL REMI INSERT — 2 MINUTES — NOT ADDED TO THE TALK

Actual application: Little Chef, whose assistant is Remi.
Repository: Little-Chef-main (your existing installation)
Documented default UI: http://localhost:8838/
Use your normal working REMI address if the installed configuration differs.

PREPARATION BEFORE SPEAKING
1. Open your actual Little Chef instance and confirm that its model is responsive.
   The repository documents 'uv run chef serve' from its root as the normal launch command.
   Nothing in this optional packet launches or reconfigures Little Chef automatically.
2. Attach 04_REMI_Source.txt using the chat's existing file-drop workflow.
3. Paste the setup prompt below. The app supports ingest_file and knowledge_search.
   Complete any ingestion approval privately during preparation, before the live segment.
4. Use the uploaded path actually returned by the UI. If a duplicate filename is renamed,
   replace uploads/04_REMI_Source.txt with that returned path in the setup prompt.
5. Rehearse the main question and inspect its source. A citation marker alone is not proof.
6. Leave a fresh conversation ready with the question copied. Save a real successful answer
   and its supporting passage as a screenshot or recording if available.
   No REMI answer or recording has been fabricated in this packet.

SETUP PROMPT — BEFORE THE EVENT, NOT DURING THE TWO-MINUTE SEGMENT
Index only the attached file uploads/04_REMI_Source.txt using ingest_file, then use
knowledge_search to confirm that its conveyor-control passage is searchable.
Do not crawl a website or sync other folders. Report the indexed source filename.

MAIN PROMPT — COPY AS ONE MESSAGE
According to the indexed document 04_REMI_Source.txt, can this application stop the
conveyor, and what is its timing based on? Use only this named source. Answer in no
more than three short sentences and cite the supporting source. Do not operate
equipment, run shell commands, or modify files.

EXPECTED SOURCE CHECK — OPERATOR REFERENCE, NOT A GENERATED REMI ANSWER
Section A says the conveyor has its own hardware control. The demo uses measured
steady belt speed to estimate arrival/clearance; it cannot command or stop the
belt and has no encoder or independent bottle/diverter position sensing.
The displayed answer and citation must support those claims. Do not coach an
incorrect answer into appearing correct on stage.

OPTIONAL FOLLOW-UP — ONLY IF REHEARSED AND THERE IS TIME
According only to 04_REMI_Source.txt, what is the measured belt speed on today's
physical setup? If the measurement is not supplied, say that it is unavailable.
Do not substitute an example or configured default for a physical measurement.

EXPECTED FOLLOW-UP CHECK
The measurement is not supplied. The model should not invent one.

STAGE CUES
0:00–0:20 — BRAD
"The next person working on this project needs to understand what the system can
do. Remi helps an engineer find relevant project knowledge and check its source."

0:20–1:00 — WESLEY
Submit the main prompt in the actual Remi app. Show the answer without scrolling
through unrelated project history. If it is slow, move to a saved successful run.

1:00–1:35 — WESLEY + BRAD
Open or display the supporting passage from section A beside the answer.
BRAD: "We can check where that answer came from. The engineer still verifies it."

1:35–2:00 — BRAD
"We have gone from a question to a relevant passage and a checkable answer.
That is the part we want to make useful in an engineer's everyday workflow."
Return to the next planned item. The follow-up question replaces part of this
time only after a timed rehearsal; it does not extend the two-minute slot.

FALLBACK
Use a genuine saved REMI answer with its source and identify it as a prior run.
If no genuine answer is available, omit the insert and retain slide 10's existing
spoken explanation. The source document alone is not evidence of a model run.

READINESS
The repository and knowledge workflow have been inspected. The upload, indexing,
local model response, response time, source display, and backup still require a
real rehearsal in the actual app. Local default health endpoints were not
reachable from the preparation session; this does not establish the state of a
separate REMI host. No service was started and no existing knowledge base changed.
```

## Public source excerpt

Save the following as 04_REMI_Source.txt and attach it through the normal chat.
It contains public event-demo documentation, not private plant material.

```text
REMI OPTIONAL DEMO SOURCE — PUBLIC EVENT DOCUMENTATION
Prepared October 22, 2026. These excerpts describe the documented main-branch sorter.
They do not certify the separately modified visual-tracking build or today's hardware setup.
The section labels organize source material for the demonstration.

[A] Conveyor control and timing
Source: https://github.com/YeChamo/part-tracking-demo-ualr/blob/main/docs/ETHERMOTION_SETUP.txt
The conveyor is controlled by its own hardware. The demo uses MEASURED steady
belt speed to predict when a bottle reaches and clears the divert point. It
does not command or stop the belt and has no encoder, belt-run input, or
independent bottle/diverter position sensing.

[B] Sources that cannot send motion
Source: https://github.com/YeChamo/part-tracking-demo-ualr/blob/main/README.txt
Choose Simulation as SOURCE, choose the pass color under Color + code, and
click Start inspection. Simulation bottles, colors, and codes are synthetic.
Simulation and recorded video cannot send hardware motion commands.

[C] Routing decisions
Source: https://github.com/YeChamo/part-tracking-demo-ualr/blob/main/README.txt
0 = PASS. Selected color; no movement by default, or the selected PASS program.
1 = REJECT / DIVERT. Different/unknown color; the selected REJECT program.
These numbers are routing decisions, not motor angles or electrical outputs.
Saved EtherMotion moves define the mechanism's actual motion.

[D] Accepted command versus completed movement
Source: https://github.com/YeChamo/part-tracking-demo-ualr/blob/main/README.txt
HTTP 202 means accepted, not movement completed. The matching run ID and drive
command-counter/stopped status establish command-level completion, not actual
shaft position or physical bottle diversion. Never resend an uncertain event
as a new bottle. Inspect that run in EtherMotion before resuming.

[E] Evidence not provided here
This packet contains no measurement of today's actual belt speed, shaft position,
physical clearance, successful bottle diversion, or power-supply current.
```

## Speaking materials

- [Optional speaker script](Optional_Demo_Speaker_Script.md).
- [Optional phone cues](Optional_Demo_Phone_Cues.md).

The real REMI answer, citation display, response timing, and laptop/venue setup
still require rehearsal. Demo programs, recordings, and the ZIP remain local.
