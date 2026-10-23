# Optional demo speaker inserts

**Brad + Wesley · prepared separately · not enabled in the main script**

Use the complete [speaker script](Speaker_Script.md) and [phone cues](Phone_Cue_Cards.md) for the current 16-slide talk. Its demo is slide 11 at 0:16–0:36. Sentiment is introduced on slide 8; REMI on slide 9. These inserts replace time within the demo block if selected. They do not extend the hour or change Wesley's supplied personal sections.

## Sentiment insert — 3 minutes

Open the separately staged local sentiment demo before the session. Wesley operates; Brad addresses the audience. The separately staged offline copy needs no installation, server, model download, or internet. Software and recordings are not included in this presentation-only publication.

**0:00–0:25 · Brad:** “We've shown what software can do with an image. Here is the same engineering question with text: if we have many comments, where should someone start looking? This is a small, explainable example of that workflow.”

**0:25–1:00 · Wesley:** Click **Try 5 negative**, then **Analyze messages**. Point to the five comments, the overall score of **−58**, and the topics.

**Brad:** “The summary gives us a place to look. Let's inspect what produced it.”

**1:00–1:35 · Wesley:** Open **Why this result?** on one comment. Point to the words contributing to the result.

**Brad:** “We can follow the summary back to the words and the original comment.”

**1:35–2:25 · Wesley:** Clear the session. Enter **The product is good.** and analyze it. The individual score is **+40**.

**Brad:** “What do you expect to happen if we add the word ‘not’?” Pause for an answer.

**Wesley:** Clear the session. Enter **The product is not good.** and analyze it. The individual score is **−40**. If both comments are retained together, their average is zero, so clear between them for this comparison.

**2:25–3:00 · Brad:** “This teaching example uses English word rules. It helps us inspect a signal, and it can still miss context or sarcasm. Our broader sentiment project uses VADER with domain vocabulary. We keep the original comments available so people can check what the scores represent.”

**Short version, 60 seconds:** Show the negative batch, analyze it, open one explanation, and make the evidence point. Omit the comparison.

**Recovery:** Show the existing recorded sentiment example, if selected locally, and identify it as a prior recording. It demonstrates the existing suite and is not a new recording of this isolated copy. Explain what is visible rather than promising an identical click sequence.

## REMI / Little Chef insert — 2 minutes

The app is **Little Chef** and its assistant is **Remi**. Use the actual app. Its documented default address is http://localhost:8838/. Source and prompts are prepared; document ingestion, model response, response time, and citation display still need a real rehearsal.

### Before the event

Attach the public source excerpt in [optional preparation](Optional_Demo_Preparation.md), saved as `04_REMI_Source.txt`, to REMI. It contains excerpts from the public bottle-demo documentation, identified by section and source URL. Ingest only that file using the setup prompt in [optional preparation](Optional_Demo_Preparation.md). Use the actual uploaded path if the app renames a duplicate. Complete ingestion before speaking. Rehearse the question and check the returned passage. Save a genuine successful answer and source if a backup is desired.

### On stage

**0:00–0:20 · Brad:** “The next person working on this project needs to understand what the system can do. Remi helps an engineer find relevant project knowledge and check its source.”

**0:20–1:00 · Wesley:** Submit this prepared question:

> According to the indexed document 04_REMI_Source.txt, can this application stop the conveyor, and what is its timing based on? Use only this named source. Answer in no more than three short sentences and cite the supporting source. Do not operate equipment, run shell commands, or modify files.

Show the actual returned answer. Section A supports the expected facts: the conveyor has its own hardware control; the documented demo cannot stop it; timing uses measured steady belt speed to estimate arrival and clearance. The document describes the main-branch sorter and does not certify a separately modified visual build.

**1:00–1:35 · Wesley:** Show the cited source and the relevant passage. If citation navigation is unavailable, display the source text beside the answer. A citation marker alone is not the evidence.

**Brad:** “We can check where that answer came from. The engineer still verifies it.”

**1:35–2:00 · Brad:** “We have gone from a question to a relevant passage and a checkable answer. That is the part we want to make useful in an engineer's everyday workflow.”

**Optional rehearsed follow-up:** Ask for today's measured belt speed. The source does not provide that measurement. Use this only if it fits within the same two minutes; the expected behavior is to acknowledge the missing information.

**Recovery:** Use a genuine saved REMI answer with the source visible and identify it as a prior run. If no genuine example is available, leave this insert out and retain the main script's slide 9 explanation. No model answer or REMI recording is included or fabricated here.

## Bridges and timing

**Bottles to sentiment · Brad:** “We've used an image to produce something a person can inspect. Here is that same engineering question with text.”

**Sentiment to REMI · Brad:** “Comments are one kind of information. Engineers also need to find answers in their project documentation. Wesley, show how Remi helps with that.”

**REMI to slide 12 · Brad:** “Across these examples, the result has to hold up when conditions change, arrive in time, and give the person using it a reason to trust it.”

| Selected option | Bottle demonstration | Sentiment | REMI | Discussion and exit |
| --- | --- | --- | --- | --- |
| Neither | Original 20-minute demo and guided discussion | — | — | Included |
| Sentiment only | 14 minutes | 3 minutes | — | 3 minutes |
| REMI only | 15 minutes | — | 2 minutes | 3 minutes |
| Both | 12 minutes | 3 minutes | 2 minutes | 3 minutes |

Keep two baseline outcomes and one planned variation. Shorten optional bottle extras and discussion to make room. Return to slide 12 by **0:36**, begin the audience activity at **0:41**, and close the story by **0:40**, show the homepage QR on slide 15, and hold the final interactive slide for activity and questions from **0:41**. The current talk remains the default until an option is deliberately chosen.
