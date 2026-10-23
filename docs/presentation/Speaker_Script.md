# Engineering at The Kinetic Group — speaker script

**Brad Daugherty + Wesley Siharath · Go 4th Fridays · October 23, 2026 · 11:30 a.m.**

17 slides, using the current deck. The full personal introduction stays over slides 1–2. Hold the cover while Brad tells the beginning; advance to CSG when the story reaches the proposal and approval. Wesley introduces himself on that same CSG slide. After the introduction, each slide develops the next part of the story. Quoted paragraphs are suggested speech. Bold stage directions are for the presenters, not for speaking aloud.

**Purpose:** Bring AI into something real and help build the next generation of manufacturing.

## One-hour route

| Clock | Slides | Focus |
| --- | --- | --- |
| 0:00–0:06 | 1–2 | Personal introduction, CSG context, handoff to Wesley |
| 0:06–0:10 | 3–6 | Original history, stakes, engineering method, portfolio |
| 0:10–0:14 | 7–10 | Inspection, sentiment, and Remi examples |
| 0:14–0:16 | 11 | Wesley's ownership story |
| 0:16–0:36 | 12 | Bottle demonstration and guided questions |
| 0:36–0:40 | 13–15 | Reliability, invitation, and personal close |
| 0:40–0:41 | 16 | Homepage QR |
| 0:41–0:49 | 17 | Interactive Audience Lab and reactions |
| 0:49–1:00 | 17 held | Open questions |

These are targets, not time to fill. The introduction can naturally take **6–8 minutes**. Allow roughly 3–4 minutes on the cover and 3–4 minutes on CSG, including Wesley's interview and GPIO story. Do not stretch either section to fill a target. Change slides at the story turns below, even if the clock differs. A still cover is intentional: look at the audience, pause, and let the story carry the opening.

Aim to reach slide 11 around 0:14 and start the demo around 0:16. Optional sentiment and REMI live demonstrations remain separate.

**Slide control:** Brad advances slides and watches the clock. Wesley operates the bottle demo. On slide 12, hold the slide while introducing the demonstration, switch to the demo application at the marked cue, then return to slide 13 after the final observation. Keep slide 17 visible throughout the final questions.

## 1. Engineering at The Kinetic Group — Brad

**On screen:** Title, names, event.

**HOLD SLIDE 1:** Tell the complete beginning, including the inspection struggle. Allow roughly 3–5 minutes. Look at the audience; no slide change is needed for the school, OCR, or inspection beats.

**Brad:** “Good morning. I'm Brad Daugherty, an electrical engineer at Remington. Most of my work is in Lonoke, and I support projects across The Kinetic Group. I'm here with Wesley Siharath.”

“Today is about bringing AI into something real and helping build the next generation of manufacturing. I want to start with how we got into this work, because I did not begin knowing how to build AI systems.”

“I started as a mechanical engineering intern. I was going to school full time in Fayetteville and working full time in Lonoke, Friday through Monday. I was learning as I went.”

“My first application used OCR to pull data off HMI web servers. That was my first AI application, and probably the worst SCADA system the world has ever seen.”

**Delivery:** Pause for the joke. If helpful: “OCR reads text from an image. An HMI is the screen people use to see and operate a machine.”

**Brad:** “At the same time, I was struggling with inspection projects. I was working with off-the-shelf systems, including Keyence and Cognex. I was told it was crazy to make our own AI, and that I needed to make those solutions work.”

“I spent nearly a year on it and could not get where I needed to go. I did not fully understand the systems. I felt defeated. I did not realize that I was walking in the shoes of experienced engineers who had struggled with these kinds of problems before me.”

“Eventually, I could not keep approaching it the same way. I proposed that we build it ourselves.”

**Delivery:** Keep this centered on your learning and your experience with that application. This is a personal introduction over the cover, not a series of new story slides.

**ADVANCE TO SLIDE 2 after:** “I proposed that we build it ourselves.” Let that sentence land, then introduce the company context before telling them what happened to the proposal.

## 2. Czechoslovak Group (CSG) — Brad → Wesley → Brad

**On screen:** CSG brand, Prague headquarters, 1995 origins, main industries, and TKG membership in Ammo+.

**HOLD SLIDE 2:** Briefly explain who CSG is, then continue the approval story and hand off to Wesley. Keep this slide visible through his introduction, interview memory, and GPIO story. Target the end of the opening around 0:06; up to 0:08 is workable.

**Brad:** “Before I tell you what happened to that proposal, this is where CSG fits. CSG stands for Czechoslovak Group. It is a global industrial and technology group headquartered in Prague, in the Czech Republic. Its roots go back to Excalibur Army in 1995, and its businesses span defense, aerospace, and automotive industries. The Kinetic Group is part of CSG Ammo+, and Remington is one of the TKG brands. Today's examples come mainly from Lonoke.”

“Under the new CSG management, the proposal to build our own system was actually approved. They told me to go get an intern.”

**Delivery:** Pause at the turn in the story.

**Brad:** “So I called Wesley. He decided to come down to central Arkansas and take on the project with me. Wesley, I've told them how I got to that phone call. Take it from here.”

**Wesley:** “Hi, I’m Wesley Siharath. I’m an engineer here at Remington. I got started as an intern focused on software, with some prototyping on machines.”

“I remember it was about eight at night, and I was stacking boxes when that interview notification came through.”

“I looked at my phone and thought, ‘Thank God, I might actually get to use this degree.’ Hearing about the projects they were working on, I saw an opportunity. It sounded interesting and exciting, so I decided to charge headfirst into something I knew very little about.”

“The first problem we tackled was GPIO. We didn’t realize the Jetson needed a patch, and then we had to figure out how to control a 24-volt relay from its low-voltage output. That was my introduction to making software actually work with a machine.”

**Delivery:** Pause after “use this degree.” Let the room hear the turn from stacking boxes to building machines. Keep the GPIO memory at the level of the story; no wiring explanation is needed. If the acronym needs one short gloss, GPIO means the computer's input/output pins. Hold slide 2 throughout.

**Wesley:** “I came on full time this February, and now I work on AI tools and machines. One of the things that drew me here was being able to build a solution and see it put to use on the floor.”

**Brad:** “That is how the two of us got into this work. We were given a chance to turn an idea into something people could use on the floor. Our part in that story is recent. The manufacturing history we are building on goes back much further.”

**ADVANCE TO SLIDE 3 after:** “goes back much further.”

**Sources for company context:** [CSG About Us](https://csg.com/en/about-us) (Prague headquarters, 1995 origins, industries); [The Kinetic Group About Us](https://www.thekineticgroup.com/aboutus.html) (Ammo+ membership), checked October 22, 2026. Brand image supplied by Brad in this chat. The AI ambition is the presenters' framing. The approval and internship details are Brad's account.

## 3. Writing the next rules — Brad

**On screen:** 1816, Lonoke 1969, NEXT. Use the timeline as the setting for your story.

**Cue:** 1816, Lonoke 1969, and our turn to contribute.

**Brad:** “Remington's history goes back to 1816. Lonoke has been part of it since 1969. We inherited generations of work in machinery and manufacturing. Our contribution is to connect that experience with cameras, controls, and software. Remington is one of five TKG ammunition brands, so the problems we support extend beyond one site.”


**Brad, transition:** “That history carries responsibility, because this is real manufacturing.”

**ADVANCE TO SLIDE 4 after:** “real manufacturing.”

## 4. The stakes are real — Brad

**On screen:** Ammunition manufacturing, propellants and primers, moving machinery, real production.

**Cue:** Real machinery, real operators, real consequences.

**Brad:** “That was part of what made those inspection projects so challenging. We work around energetic materials and moving machinery. That makes timing, clear information, and recovery part of the engineering problem. We build with operators, maintenance, quality, and safety. The software has to fit their workflow and the established safeguards.”

**Brad, transition:** “So what does it take for software to reach that floor?”

**ADVANCE TO SLIDE 5 after:** “reach that floor?”

## 5. Engineering that reaches the floor — Brad

**On screen:** SENSE / DECIDE / ACT. Connect each word to the whole system you had to build.

**Cue:** Capture, inference, decision, response.

**Brad:** “When we proposed building it ourselves, this was the whole problem we were taking on. Sense, decide, act. For a vision system, that means acquiring an image, running inference, interpreting the output, and delivering a result in time for the workflow. A model result is one step in that chain. Camera conditions, signals, software latency, and the response all have to fit together. We test the whole chain and show people the evidence behind the result.”

**Brad, transition:** “You can see that same pattern across our work.”

**ADVANCE TO SLIDE 6 after:** “across our work.”

## 6. The work spans the organization — Brad

**On screen:** Two production inspection systems and two other capabilities. Give the room a brief map.

**Cue:** Two live inspection systems, two broader capabilities. Finish this context block by about 0:10.

**Brad:** “That approach now connects the different kinds of work we do. Centerfire and shotshell inspection are live and still being refined. Public sentiment and Remi apply software to different questions: what customers are saying, and how engineers find project knowledge. The common problem is making the evidence useful to someone making a decision.”

**Brad, transition:** “Start with centerfire inspection and what building that capability involves.”

**ADVANCE TO SLIDE 7 after:** the centerfire introduction. Finish this overview around 0:10.

## 7. Centerfire inspection — Brad → Wesley → Brad

**On screen:** Image capture, inference, a usable result, and earning trust. Explain what building our own involves.

**Cue:** Vision pipeline, visible evidence, operator trust.

**Brad:** “Here is what building our own system involves. Remington Vision brings image capture, labeling, model training, and inference into one toolset. It uses YOLOX detection models and supports workstation and edge deployment. The model is only part of the system. The result has to reach a usable workflow, and people need to understand what the camera saw.”

**Wesley:** “On the floor we show operators what the system sees, listen when something is confusing, and make changes they can judge for themselves.”

**Brad:** “That feedback is part of commissioning and continued improvement. It is how the technical result earns trust.”

**Brad, transition:** “Carrying that tooling into another product still leaves a different engineering problem. Wesley, take shotshell.”

**ADVANCE TO SLIDE 8 after:** “take shotshell.”

## 8. Shotshell inspection — Wesley → Brad

**On screen:** A different product, different data and view. Wesley explains why reuse still requires engineering.

**Cue:** A different product changes the image and the data.

**Wesley:** “One thing Remington Vision taught me is how much work happens before you even train the model. You have to figure out what the camera can actually see, collect useful examples, and label them consistently.”

“When we move to a different product, those questions come up again. We can carry over the software and what we’ve learned, but we still have to get the images and testing right for that application.”

“That’s something I enjoy about this work. Every problem we figure out gives us a better starting point for the next one—and there’s always something new to learn.”

**Wesley handback:** Finish on “there’s always something new to learn.” Pause and look to Brad. Keep slide 8 visible until Brad's transition.

**Brad:** “This is also live and being refined. Reusing software still leaves real integration work.”

**Brad, transition:** “Those are image problems on the floor. Other teams need help making sense of text.”

**ADVANCE TO SLIDE 9 after:** “making sense of text.”

## 9. Public sentiment — Brad

**On screen:** Public discussion, themes, source links. Brief overview; no optional live insert is enabled.

**Cue:** Collect, score, retain the source.

**Brad:** “The same need to turn information into a useful decision also shows up away from the production line. The sentiment project collects public discussion, scores sentiment and product themes, and stores the results for review. The scoring uses VADER with a domain vocabulary. A trend gives the team somewhere to investigate. Keeping the original comments available lets people check what the score actually represents.”

**Brad, transition:** “Public comments are one source. Our own project documents are another. Wesley?”

**ADVANCE TO SLIDE 10 after:** “Wesley?”

## 10. Remi — Wesley → Brad

**On screen:** Project documents, retrieval, citations, local model, scoped tools. Brief overview.

**Cue:** Retrieve project material, generate an answer, check the source.

**Wesley:** “Another kind of information we work with is project documentation. Remi uses a local language model with retrieval over approved project documents. It indexes the material, finds relevant passages, and answers with citations. Scoped tools let it work within a defined workspace. The engineer still checks the source and the result.”

**Brad:** “Here the integration problem is keeping the answer connected to evidence and controlling what the tools can do.”

**Brad, transition:** “Those are the projects. The part that keeps us interested is getting to carry an idea into use.”

**ADVANCE TO SLIDE 11 after:** “carry an idea into use.”

## 11. Why we love this work — Brad → Wesley → Brad

**On screen:** Variety, freedom, ownership, growth. This is where Wesley tells his real-reject moment.

**Cue:** Variety, freedom, ownership, and a real result. Demo at 0:16.

**Brad:** “We have shown you the kinds of work. Wesley, what do you enjoy most about actually doing it here?”

**Wesley:** “What I love most is the variety of problems we face day to day. One day I might be debugging code in the office. Another day I might be knee-deep in grease, figuring out why a machine’s motor isn’t spinning.”

“I also enjoy the freedom to spitball an idea, explore different solutions, and take ownership of how we tackle the problem.”

“One moment that really stuck with me was seeing a real reject come through and watching our system toss it out. Seeing something I helped build actually do its job was an amazing feeling.”

“Brad started calling that dented shell his child. I remember him being happy about it for a week straight.”

**Delivery:** Pause for the laugh, then finish the ownership thought.

“Following ideas through and seeing people get invested feels like helping pave the way for Remington. I enjoy figuring it out.”

**Brad:** “Let's show that connection between an image, a decision, and a visible result.”

**ADVANCE TO SLIDE 12 after:** “a visible result.” Target 0:16. Keep Wesley's real-reject moment here so it lands once.

## 12. Live demonstration — Brad + Wesley

**On screen:** CAMERA → AI → ACTION and Gatorade bottles. Hold this while framing the demo, then switch applications.

**Cue:** Detection, color prediction, track, decision, one variation. 0:16–0:36.

**Before the event:** Rehearse the exact application build, camera, two bottles, and one variation. The repository's standard mode uses YOLOX bottle detection and a trained color model. A visual-tracking build can instead show boxes, labels, and track identity; use the rehearsed outcomes of the actual build. The generic bundled bottle locator does not predict colors. Describe the mode actually shown. Keep the core demonstration on screen; include physical movement only if the complete event setup has been validated.

**Opening, 2 minutes. Brad:** “This is a separate event demo using Gatorade bottles, a small example of AI becoming something useful in manufacturing. We detect the bottle, associate evidence with its track, and apply a color rule to produce an on-screen sort decision. First, predict the result. Then we will change one condition and look at what happened.”

**Application cue:** Show slide 12 for the opening, then say, “Wesley, let's look at it.” Switch to the rehearsed demo application before the baseline.

**Baseline, 4 minutes. Brad** states the pass color and asks for predictions for two contrasting bottles. **Wesley** points out the bottle box, model color prediction, track, and displayed decision. In the standard repository mode, unknown color diverts. Show what this build actually did.

**Variation, 4 minutes.** Change one pretested orientation or position. Ask for a prediction. Compare the evidence with the baseline. If the result is surprising: “That gives us something useful to test.”

**Engineering discussion, 8 minutes. Brad:** “What would you test before relying on this all day?” **Wesley** connects answers to lighting, missed detections, timing, and the information an operator needs. If confidence comes up, explain that the model score is not automatically a calibrated probability. If physical timing comes up, explain that the demo estimates arrival from distance and measured speed; it does not independently measure physical actuator position.

**Transition, 2 minutes. Brad:** “The image, model, tracking, and response each have to hold up. Wesley's experience on the floor is where those requirements become concrete.” Return to slide 13 by 0:36.

**Recovery:** Show the camera view and last successful result. Ask what the audience would inspect first. Move on within two minutes. Optional barcodes and physical motion are outside the core sequence.

**RETURN TO THE DECK AT SLIDE 13** after the demo transition. Do not move through the sentiment or Remi slides again.

## 13. The hard problems — Brad → Wesley → Brad

**On screen:** Variation, timing, reliability. Return here from the application after the demo.

**Cue:** Timing, signals, sunlight, and confidence.

**Brad:** “Wesley, what are the hardest problems in getting these systems to work reliably on the floor?”

**Wesley:** “Some of the hardest problems in any system are the little things. Is the machine timed correctly? Is it getting the right signal at the moment it needs it? Or is something downstream causing an issue?”

“Then you have changing conditions. Something as simple as sunlight coming through a window could blind your cameras for thirty minutes.”

“You have to work through those issues so the whole system keeps working as conditions change. It needs to be reliable enough to leave your hands, and the people using it need confidence that it will keep doing its job.”

“Building that reliability and confidence takes work.”

**Brad:** “That is the step from a prototype we operate ourselves to a system other people can rely on.”

**Brad, transition:** “Working through those problems takes people with different skills. That is where the next person can come in.”

**ADVANCE TO SLIDE 14 after:** “the next person can come in.”

## 14. Come fight for what is next — Brad

**On screen:** Mechanical, controls, software, testing. Tie the invitation to how Brad and Wesley started.

**Cue:** Mechanical, controls, software, and testing. Close before the two final QR slides.

**Brad:** “I started as a mechanical engineering intern trying to solve a problem I did not understand. Wesley started through software and machine prototyping. Building the next generation of manufacturing needs people from all of those directions. These problems cross mechanical engineering, controls, software, and testing. We want people who will follow a problem from the first question through deployment and improvement. Tell us what you have built and what you want to take on next.”

**Brad, transition:** “If that sounds like the kind of work you want to do, come talk to us.”

**ADVANCE TO SLIDE 15 after:** “come talk to us.”

## 15. Let us connect — Brad → Wesley → Brad

**On screen:** Factory-floor closing message and awhite@tkghunt.com. Close the story before the QR slides.

**Cue:** awhite@tkghunt.com, questions, internship, and ideas. Close the story by about 0:40, before the homepage and lab QR slides.

**Brad:** “Reach us at **awhite@tkghunt.com**. We’ll be here afterward if anyone wants to connect. Wesley, anything you’d like to add?”

**Wesley:** “Yeah, if you guys have any engineering questions or want to hear more about my internship experience, come talk with us afterward. I’d love to hear what you’re building and spitball some ideas with you.”

**Brad:** “For me, this started with a rough OCR application and a problem I could not solve. Then we got the chance to try, and I called Wesley. That is what I hope you take from our story: you can start while you are still learning, find people to build with, and keep working until the result is useful to someone else. Our history was made on the factory floor. The future will be, too. Come help us bring AI into real work and build the next generation of manufacturing.”


**Bridge:** “Before we finish, here are two ways to keep exploring.”

**ADVANCE TO SLIDE 16 after:** “two ways to keep exploring.” Aim to close the personal story around 0:40.

## 16. Explore 4Founders — Brad

**On screen:** Homepage QR and 4founders.dev. Pause for people to scan.

**Cue:** Penultimate slide. Homepage QR, about 0:40–0:41.

**Brad:** “This code takes you to the 4Founders home page: **4founders.dev**. You can open it now or save it for later.”

Pause for a scan. The QR encodes **https://4founders.dev/**. Do not promise unverified homepage features.

**Bridge:** “The last slide takes you straight to the interactive demo.”

**ADVANCE TO SLIDE 17 after:** “straight to the interactive demo.” Allow time for the homepage scan first.

## 17. 4Founders challenge — Brad + Wesley

**On screen:** Interactive lab QR, URL, and PIN 877262. Hold through the activity and open questions.

**Cue:** Scan, PIN, try, share. 0:41–0:49.

**Brad:** “Scan the QR code or open the URL on screen. Enter PIN **877262**. Try the Audience Lab and notice what matches or surprises your expectations.”

Give **4–5 minutes**. Wesley helps with access. Brad keeps the QR and PIN visible, then takes **two or three observations**. Ask: “What would you change before people used this every day?”

**Backup URL:** [4founders.dev/demo/ai-in-action/](https://4founders.dev/demo/ai-in-action/). Recheck access and scan before the event. If access fails, show one prepared example and ask the room to predict it.


**Questions, 0:49–1:00:** Keep this final slide visible so the lab QR, URL, and PIN remain available. “What are you curious about, or what are you trying to build?”

**HOLD SLIDE 17:** Keep the QR, URL, and PIN visible during the activity and questions. No further slide change.

## Source and status notes

The supplied deck and Brad's project descriptions establish the company context and that the two inspection systems are live and still being refined. Remington's [company history](https://www.remington.com/about-us.html) and [employee history](https://www.remington.com/big-green-blog/labor-day-special.html) are the existing sources for the 1816 origin and 1969 Lonoke start.

Technical descriptions were checked against the supplied local project documentation: RemingtonVision README (capture, labeling, YOLOX training/inference, and deployment options); Public Sentiment README (collection, VADER/domain scoring, storage, and dashboard); Little Chef README and docs/KNOWLEDGE.md (local model, retrieval, citations, and scoped tools). These describe software capabilities, not a claim that every feature is deployed on every production line. No inspection criteria, process settings, performance metrics, or production architecture have been added.

The bottle demo description follows the [repository README](https://github.com/YeChamo/part-tracking-demo-ualr/blob/main/README.md). This revision does not establish live hardware, camera, or venue readiness. Wesley supplied his introduction, interview-notification and GPIO story, dented-shell moment, next-application lesson, reliability examples, and closing invitation. His new story wording is retained. The original worksheet used an earlier slide order; these memories now belong to slides 2, 11, and 8 respectively. The GPIO and relay account is a personal recollection, not equipment instructions or a claim about the event demo's hardware.


Brad's personal introduction comes from his account supplied in this chat: mechanical engineering internship, full-time school in Fayetteville and work in Lonoke Friday–Monday, OCR from HMI web servers, inspection struggles with Keyence/Cognex, CSG approval, and the call to Wesley. The historical OCR/SCADA anecdote does not reintroduce a standalone SCADA project slide. CSG context is sourced in slide 2 notes. The AI/next-generation ambition is the presenters' framing.
