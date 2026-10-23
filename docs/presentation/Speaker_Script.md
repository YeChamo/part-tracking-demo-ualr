# Engineering at The Kinetic Group — speaker script

**Brad Daugherty + Wesley Siharath · Go 4th Fridays · October 23, 2026 · 11:30 a.m.**

17 slides. The company/project slides return to their original visual flow. Brad's personal introduction runs over the cover and the new CSG slide. The speech does not need to describe each slide literally. Wesley has space to add his own memory of the call; his supplied personal wording remains intact. Quoted paragraphs are suggested speech, and other lines are operator or delivery cues.

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

These are targets, not time to fill. Let the introduction breathe, then move through the familiar slides. Optional sentiment and REMI demonstrations remain separate.

## 1. Engineering at The Kinetic Group — Brad

**Cue:** Use the cover as a visual anchor for your personal introduction. Do not advance for every story beat. About 3 minutes, with room to speak naturally.

**Brad:** “Good morning. I'm Brad Daugherty, an electrical engineer at Remington. Most of my work is in Lonoke, and I support projects across The Kinetic Group. I'm here with Wesley Siharath.”

“Today is about bringing AI into something real and helping build the next generation of manufacturing. I want to start with how we got into this work, because I did not begin knowing how to build AI systems.”

“I started as a mechanical engineering intern. I was going to school full time in Fayetteville and working full time in Lonoke, Friday through Monday. I was learning as I went.”

“My first application used OCR to pull data off HMI web servers. That was my first AI application, and probably the worst SCADA system the world has ever seen.”

**Delivery:** Pause for the joke. If helpful: “OCR reads text from an image. An HMI is the screen people use to see and operate a machine.”

**Brad:** “At the same time, I was struggling with inspection projects. I was working with off-the-shelf systems, including Keyence and Cognex. I was told it was crazy to make our own AI, and that I needed to make those solutions work.”

“I spent nearly a year on it and could not get where I needed to go. I did not fully understand the systems. I felt defeated. I did not realize that I was walking in the shoes of experienced engineers who had struggled with these kinds of problems before me.”

“Eventually, I could not keep approaching it the same way. I proposed that we build it ourselves.”

**Delivery:** Keep this centered on your learning and your experience with that application. This is a personal introduction over the cover, not a series of new story slides.

**Bridge:** Advance to the CSG slide for the company context and the opportunity to try.

## 2. Czechoslovak Group (CSG) — Brad → Wesley → Brad

**Cue:** CSG context, approval, and the call to Wesley. Complete the personal introduction by about 0:06.

**Brad:** “CSG stands for Czechoslovak Group. It is a global industrial and technology group headquartered in Prague, in the Czech Republic. Its roots go back to Excalibur Army in 1995, and its businesses span defense, aerospace, and automotive industries. The Kinetic Group is part of CSG Ammo+, and Remington is one of the TKG brands. Today's examples come mainly from Lonoke.”

“Under the new CSG management, the proposal to build our own system was actually approved. They told me to go get an intern.”

**Delivery:** Pause at the turn in the story.

**Brad:** “So I called Wesley. He decided to come down to central Arkansas and take on the project with me. Wesley, I've told them how I got to that phone call. Tell them your part of the story.”

**Wesley:** “Hi, I’m Wesley Siharath. I’m an engineer here at Remington. I got started as an intern focused on software, with some prototyping on machines.”

“I came on full time this February, and now I work on AI tools and machines. One of the things that drew me here was being able to build a solution and see it put to use on the floor.”

**Wesley's optional story slot, 30–60 seconds:** [Add your own memory of the call, coming to central Arkansas, or the first problem you tackled together. The supplied introduction works without an added anecdote.]

**Brad:** “We want to turn that opportunity into useful capability on the floor. That is how we want to help build the next generation of manufacturing. Here is the company and the work that story sits inside.”

**Sources for company context:** [CSG About Us](https://csg.com/en/about-us) (Prague headquarters, 1995 origins, industries); [The Kinetic Group About Us](https://www.thekineticgroup.com/aboutus.html) (Ammo+ membership), checked October 22, 2026. Brand image supplied by Brad in this chat. The AI ambition is the presenters' framing. The approval and internship details are Brad's account.

## 3. Writing the next rules — Brad

**Cue:** 1816, Lonoke 1969, and our turn to contribute.

**Brad:** “Remington's history goes back to 1816. Lonoke has been part of it since 1969. We inherited generations of work in machinery and manufacturing. Our contribution is to connect that experience with cameras, controls, and software. Remington is one of five TKG ammunition brands, so the problems we support extend beyond one site.”


**Bridge from the personal introduction:** The slides now return to the original company/project flow. Use the history as context rather than retelling the internship.

## 4. The stakes are real — Brad

**Cue:** Real machinery, real operators, real consequences.

**Brad:** “We work around energetic materials and moving machinery. That makes timing, clear information, and recovery part of the engineering problem. We build with operators, maintenance, quality, and safety. The software has to fit their workflow and the established safeguards.”

## 5. Engineering that reaches the floor — Brad

**Cue:** Capture, inference, decision, response.

**Brad:** “Sense, decide, act. For a vision system, that means acquiring an image, running inference, interpreting the output, and delivering a result in time for the workflow. A model result is one step in that chain. Camera conditions, signals, software latency, and the response all have to fit together. We test the whole chain and show people the evidence behind the result.”

## 6. The work spans the organization — Brad

**Cue:** Two live inspection systems, two broader capabilities. Finish this context block by about 0:10.

**Brad:** “Centerfire and shotshell inspection are live and still being refined. Public sentiment and Remi apply software to different questions: what customers are saying, and how engineers find project knowledge. The common problem is making the evidence useful to someone making a decision.”

## 7. Centerfire inspection — Brad → Wesley → Brad

**Cue:** Vision pipeline, visible evidence, operator trust.

**Brad:** “Remington Vision brings image capture, labeling, model training, and inference into one toolset. It uses YOLOX detection models and supports workstation and edge deployment. The model is only part of the system. The result has to reach a usable workflow, and people need to understand what the camera saw.”

**Wesley:** “On the floor we show operators what the system sees, listen when something is confusing, and make changes they can judge for themselves.”

**Brad:** “That feedback is part of commissioning and continued improvement. It is how the technical result earns trust.”

## 8. Shotshell inspection — Wesley → Brad

**Cue:** A different product changes the image and the data.

**Wesley:** “A different product creates a different visual problem. We have to check the camera view, the examples used to train and test the model, and how the result fits the line. We carry the tooling forward, then validate the application in its own conditions.”

**Brad:** “This is also live and being refined. Reusing software still leaves real integration work.”

## 9. Public sentiment — Brad

**Cue:** Collect, score, retain the source.

**Brad:** “The sentiment project collects public discussion, scores sentiment and product themes, and stores the results for review. The scoring uses VADER with a domain vocabulary. A trend gives the team somewhere to investigate. Keeping the original comments available lets people check what the score actually represents.”

## 10. Remi — Wesley → Brad

**Cue:** Retrieve project material, generate an answer, check the source.

**Wesley:** “Remi uses a local language model with retrieval over approved project documents. It indexes the material, finds relevant passages, and answers with citations. Scoped tools let it work within a defined workspace. The engineer still checks the source and the result.”

**Brad:** “Here the integration problem is keeping the answer connected to evidence and controlling what the tools can do.”

## 11. Why we love this work — Brad → Wesley → Brad

**Cue:** Variety, freedom, ownership, and a real result. Demo at 0:16.

**Brad:** “Wesley, what do you enjoy most about working here?”

**Wesley:** “What I love most is the variety of problems we face day to day. One day I might be debugging code in the office. Another day I might be knee-deep in grease, figuring out why a machine’s motor isn’t spinning.”

“I also enjoy the freedom to spitball an idea, explore different solutions, and take ownership of how we tackle the problem.”

“One moment that really stuck with me was seeing a real reject come through and watching our system toss it out. Seeing something I helped build actually do its job was an amazing feeling.”

“Following ideas through and seeing people get invested feels like helping pave the way for Remington. I enjoy figuring it out.”

**Brad:** “Let's show that connection between an image, a decision, and a visible result.”

## 12. Live demonstration — Brad + Wesley

**Cue:** Detection, color prediction, track, decision, one variation. 0:16–0:36.

**Before the event:** Rehearse the exact application build, camera, two bottles, and one variation. The repository's standard mode uses YOLOX bottle detection and a trained color model. A visual-tracking build can instead show boxes, labels, and track identity; use the rehearsed outcomes of the actual build. The generic bundled bottle locator does not predict colors. Describe the mode actually shown. Keep the core demonstration on screen; include physical movement only if the complete event setup has been validated.

**Opening, 2 minutes. Brad:** “This is a separate event demo using Gatorade bottles, a small example of AI becoming something useful in manufacturing. We detect the bottle, associate evidence with its track, and apply a color rule to produce an on-screen sort decision. First, predict the result. Then we will change one condition and look at what happened.”

**Baseline, 4 minutes. Brad** states the pass color and asks for predictions for two contrasting bottles. **Wesley** points out the bottle box, model color prediction, track, and displayed decision. In the standard repository mode, unknown color diverts. Show what this build actually did.

**Variation, 4 minutes.** Change one pretested orientation or position. Ask for a prediction. Compare the evidence with the baseline. If the result is surprising: “That gives us something useful to test.”

**Engineering discussion, 8 minutes. Brad:** “What would you test before relying on this all day?” **Wesley** connects answers to lighting, missed detections, timing, and the information an operator needs. If confidence comes up, explain that the model score is not automatically a calibrated probability. If physical timing comes up, explain that the demo estimates arrival from distance and measured speed; it does not independently measure physical actuator position.

**Transition, 2 minutes. Brad:** “The image, model, tracking, and response each have to hold up. Wesley's experience on the floor is where those requirements become concrete.” Return to slide 13 by 0:36.

**Recovery:** Show the camera view and last successful result. Ask what the audience would inspect first. Move on within two minutes. Optional barcodes and physical motion are outside the core sequence.

## 13. The hard problems — Brad → Wesley → Brad

**Cue:** Timing, signals, sunlight, and confidence.

**Brad:** “Wesley, what are the hardest problems in getting these systems to work reliably on the floor?”

**Wesley:** “Some of the hardest problems in any system are the little things. Is the machine timed correctly? Is it getting the right signal at the moment it needs it? Or is something downstream causing an issue?”

“Then you have changing conditions. Something as simple as sunlight coming through a window could blind your cameras for thirty minutes.”

“You have to work through those issues so the whole system keeps working as conditions change. It needs to be reliable enough to leave your hands, and the people using it need confidence that it will keep doing its job.”

“Building that reliability and confidence takes work.”

**Brad:** “That is the step from a prototype we operate ourselves to a system other people can rely on.”

## 14. Come fight for what is next — Brad

**Cue:** Mechanical, controls, software, and testing. Close before the two final QR slides.

**Brad:** “Building the next generation of manufacturing means connecting AI to real work. These problems cross mechanical engineering, controls, software, and testing. We want people who will follow a problem from the first question through deployment and improvement. Tell us what you have built and what you want to take on next.”

## 15. Let us connect — Brad → Wesley → Brad

**Cue:** awhite@tkghunt.com, questions, internship, and ideas. Close the story by about 0:40, before the homepage and lab QR slides.

**Brad:** “Reach us at **awhite@tkghunt.com**. We’ll be here afterward if anyone wants to connect. Wesley, anything you’d like to add?”

**Wesley:** “Yeah, if you guys have any engineering questions or want to hear more about my internship experience, come talk with us afterward. I’d love to hear what you’re building and spitball some ideas with you.”

**Brad:** “The generations before us built the foundation. We want to build what the next generation can stand on. Our history was made on the factory floor. The future will be, too. Let's bring AI into real work and build the next generation of manufacturing together. Come build and fight with us. Turn AI into action.”


**Bridge:** “Before we finish, here are two ways to keep exploring.”

## 16. Explore 4Founders — Brad

**Cue:** Penultimate slide. Homepage QR, about 0:40–0:41.

**Brad:** “This code takes you to the 4Founders home page: **4founders.dev**. You can open it now or save it for later.”

Pause for a scan. The QR encodes **https://4founders.dev/**. Do not promise unverified homepage features.

**Bridge:** “The last slide takes you straight to the interactive demo.”

## 17. 4Founders challenge — Brad + Wesley

**Cue:** Scan, PIN, try, share. 0:41–0:49.

**Brad:** “Scan the QR code or open the URL on screen. Enter PIN **877262**. Try the Audience Lab and notice what matches or surprises your expectations.”

Give **4–5 minutes**. Wesley helps with access. Brad keeps the QR and PIN visible, then takes **two or three observations**. Ask: “What would you change before people used this every day?”

**Backup URL:** [4founders.dev/demo/ai-in-action/](https://4founders.dev/demo/ai-in-action/). Recheck access and scan before the event. If access fails, show one prepared example and ask the room to predict it.


**Questions, 0:49–1:00:** Keep this final slide visible so the lab QR, URL, and PIN remain available. “What are you curious about, or what are you trying to build?”

## Source and status notes

The supplied deck and Brad's project descriptions establish the company context and that the two inspection systems are live and still being refined. Remington's [company history](https://www.remington.com/about-us.html) and [employee history](https://www.remington.com/big-green-blog/labor-day-special.html) are the existing sources for the 1816 origin and 1969 Lonoke start.

Technical descriptions were checked against the supplied local project documentation: RemingtonVision README (capture, labeling, YOLOX training/inference, and deployment options); Public Sentiment README (collection, VADER/domain scoring, storage, and dashboard); Little Chef README and docs/KNOWLEDGE.md (local model, retrieval, citations, and scoped tools). These describe software capabilities, not a claim that every feature is deployed on every production line. No inspection criteria, process settings, performance metrics, or production architecture have been added.

The bottle demo description follows the [repository README](https://github.com/YeChamo/part-tracking-demo-ualr/blob/main/README.md). This revision does not establish live hardware, camera, or venue readiness. Wesley supplied his four personal sections; his wording is retained.


Brad's personal introduction comes from his account supplied in this chat: mechanical engineering internship, full-time school in Fayetteville and work in Lonoke Friday–Monday, OCR from HMI web servers, inspection struggles with Keyence/Cognex, CSG approval, and the call to Wesley. The historical OCR/SCADA anecdote does not reintroduce a standalone SCADA project slide. CSG context is sourced in slide 2 notes. The AI/next-generation ambition is the presenters' framing.
