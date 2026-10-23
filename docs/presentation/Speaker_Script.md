# Engineering at The Kinetic Group — our story

**Brad Daugherty + Wesley Siharath · Go 4th Fridays · October 23, 2026 · 11:30 a.m.**

16 slides. Brad advances slides and watches time. The story begins with Brad's mechanical engineering internship and hands over to Wesley at slide 5. Quoted paragraphs are suggested spoken words. Bracketed story prompts belong to Wesley to fill in; they are not claims about what happened. His previously supplied personal wording is retained across the relevant slides.

## One-hour route

| Clock | Slides | Focus |
| --- | --- | --- |
| 0:00–0:08 | 1–4 | OCR, school and work, inspection frustration, approval to build |
| 0:08–0:14 | 5–9 | Wesley's arrival, a real result, and where the work led |
| 0:14–0:16 | 10 | Why we love the work |
| 0:16–0:36 | 11 | Bottle demonstration and guided engineering questions |
| 0:36–0:40 | 12–14 | Reliability, invitation, and personal close |
| 0:40–0:41 | 15 | 4Founders homepage QR |
| 0:41–0:49 | 16 | Interactive Audience Lab, then reactions |
| 0:49–1:00 | 16 held | Questions with the interactive QR and PIN still visible |

These are targets. Protect the demo exit at 0:36 and the final activity at 0:41. Shorten the sentiment and Remi descriptions if needed. Their optional live inserts remain separate and are not enabled by this script.

**Story to remember:** I started without knowing how. I struggled. Someone gave us a chance. I called Wesley. Together we learned what it takes to make the work useful and reliable.

## 1. Engineering at The Kinetic Group — Brad

**Cue:** Introduce the people, then begin where you actually started.

**Brad:** “Good morning. I'm Brad Daugherty, an electrical engineer at Remington. Most of my work is in Lonoke, and I support projects across The Kinetic Group. This is Wesley Siharath, who helped start our Remington Vision work.”

“We could spend this hour showing you a list of projects. I want to start with how we got here, because I did not begin as somebody who knew how to build AI systems.”

**Bridge:** “I started as a mechanical engineering intern.”

## 2. My first AI application — Brad

**Cue:** Mechanical intern. Full-time school in Fayetteville. Full-time work in Lonoke, Friday–Monday. OCR.

**Brad:** “I was a mechanical engineering intern, going to school full time in Fayetteville and working full time in Lonoke, Friday through Monday. I did not know what I was doing yet. I was learning as I went.”

“The first application was OCR: pulling data off HMI web servers. That was my first AI application, and probably the worst SCADA system the world has ever seen.”

**Delivery:** Pause after the joke. Let the room react; do not explain it twice. For anyone unfamiliar with the terms: “OCR reads text from an image. An HMI is the screen people use to see and operate a machine.”

**Brad:** “It was rough, but I was building something around a problem I could see. At the same time, I was struggling with inspection projects.”

## 3. A year of trying — Brad

**Cue:** Off-the-shelf inspection. Keyence and Cognex. Frustration and perspective.

**Brad:** “I was working with off-the-shelf inspection systems, including Keyence and Cognex. I was told it was crazy to make our own AI, and that I needed to make the existing solutions work.”

“I spent nearly a year on it and could not get where I needed to go. I did not fully understand the systems. I felt defeated.”

“What I did not appreciate at the time was that I was walking in the shoes of experienced engineers who had struggled with these kinds of problems before me. I thought I was the problem.”

**Delivery:** This is your experience with that application and your learning at the time. Keep the emphasis on what you struggled to understand and accomplish. Let the pause after “defeated” carry the moment.

**Bridge:** “Eventually, I could not keep approaching it the same way.”

## 4. A chance to build it ourselves — Brad

**Cue:** Propose another approach. New CSG management approves. Go get an intern.

**Brad:** “I proposed that we build it ourselves. Under the new CSG management, that proposal was actually approved.”

“They told me to go get an intern.”

**Delivery:** Pause. This is the turn in the story.

**Brad:** “So I called Wesley. He decided to come down to central Arkansas and take on the project with me.”

## 5. Then I called Wesley — Brad → Wesley

**Cue:** Give Wesley ownership of the next chapter.

**Brad:** “Wesley, I've told them how I got to that phone call. Take it from here. Tell them how you got started and where the project went from there.”

**Wesley:** “Hi, I’m Wesley Siharath. I’m an engineer here at Remington. I got started as an intern focused on software, with some prototyping on machines.”

“I came on full time this February, and now I work on AI tools and machines. One of the things that drew me here was being able to build a solution and see it put to use on the floor.”

**Wesley's story slot, 30–60 seconds:** [Add your own memory of Brad's call, coming to central Arkansas, or the first problem you tackled together. What did you think you were taking on? Choose one real moment; the short introduction above is enough if you do not add a story.]

**Bridge for Wesley:** “The moment that made it real for me was seeing the system do its job.”

## 6. Seeing it do its job — Wesley → Brad

**Cue:** Centerfire inspection. The real reject is the payoff.

**Wesley:** “One moment that really stuck with me was seeing a real reject come through and watching our system toss it out. Seeing something I helped build actually do its job was an amazing feeling.”

**Wesley's story slot, up to 30 seconds:** [What could the room picture about that moment? Add what you personally saw or felt. Do not invent performance numbers or describe an unapproved inspection criterion.]

**Brad:** “That is the connection we had been trying to make: an image, a model result, and something useful happening on the floor. The tools now cover image capture, labeling, model training, and inference with YOLOX detection models.”

**Wesley:** “On the floor we show operators what the system sees, listen when something is confusing, and make changes they can judge for themselves.”

**Brad:** “The result working is a milestone. Earning the confidence of the people using it is more work.”

## 7. One project teaches the next — Wesley → Brad

**Cue:** Shotshell inspection. Reuse the tooling; learn the application again.

**Wesley:** “A different product creates a different visual problem. We have to check the camera view, the examples used to train and test the model, and how the result fits the line. We carry the tooling forward, then validate the application in its own conditions.”

**Optional Wesley story slot:** [One short example of something that had to change for the different product. Use an example you are comfortable sharing.]

**Brad:** “Centerfire and shotshell inspection are live and still being refined. What we learned on one project gave us a starting point for the next, and the next application still had to earn its result.”

## 8. The questions got broader — Brad

**Cue:** Public sentiment. A brief example of where the same approach led.

**Brad:** “The questions grew beyond images of parts. Sometimes the information is what people are saying publicly about products. The sentiment project collects discussion, uses VADER with domain vocabulary to score it, and keeps the original comments available.”

“The same lesson applies: give somebody a useful place to investigate, and let them inspect the evidence.”

**Delivery:** Keep this to about 30–45 seconds. The optional sentiment demonstration is prepared separately; it is not part of this default sequence.

## 9. Finding what we already know — Wesley → Brad

**Cue:** Remi / Little Chef. Project knowledge with sources.

**Wesley:** “Remi uses a local language model with retrieval over approved project documents. It indexes the material, finds relevant passages, and answers with citations. Scoped tools let it work within a defined workspace. The engineer still checks the source and the result.”

**Brad:** “As the work grows, finding what we already know becomes another engineering problem. We want the answer to stay connected to the evidence behind it.”

**Delivery:** Keep this brief. The optional REMI demonstration remains separate and needs a real rehearsal before use.

## 10. Why we love this work — Brad → Wesley → Brad

**Cue:** Variety, freedom, ownership. Start the demo at 0:16.

**Brad:** “Wesley, what do you enjoy most about working here?”

**Wesley:** “What I love most is the variety of problems we face day to day. One day I might be debugging code in the office. Another day I might be knee-deep in grease, figuring out why a machine’s motor isn’t spinning.”

“I also enjoy the freedom to spitball an idea, explore different solutions, and take ownership of how we tackle the problem.”

“Following ideas through and seeing people get invested feels like helping pave the way for Remington. I enjoy figuring it out.”

**Brad:** “That is what being given a chance opened up for us. Let's show you a small example of the work.”

## 11. What we learned, live — Brad + Wesley

**Cue:** The demo illustrates the story. 0:16–0:36.

**Before the event:** Rehearse the exact application build, camera, props, and one variation. Describe only the mode being shown. The documented standard sorter uses trained color predictions; a generic bottle locator alone cannot predict colors. A visual-tracking build can show boxes, labels, and track identity without color sorting. Include physical action only after the complete event setup is validated. The event setup is separate from the production inspection systems.

**Opening, about 2 minutes. Brad:** “These bottles give us a simple way to show the kind of work we have been talking about. Watch what the camera sees, what the software produces, and what changes when we change a condition. First, make a prediction.”

**Baseline, about 4 minutes:** Show two clear observations or outcomes supported by the actual build. Wesley points to the box, label or model evidence, tracked identity, and any actual decision. If showing a tested sorting mode, Brad states the pass rule and contrasts two bottles. If showing tracking, use the rehearsed identity/position sequence. Call a displayed decision on-screen; describe a physical action only when it actually occurs.

**One planned variation, about 4 minutes:** Change one rehearsed orientation, position, or other condition. Ask for a prediction and compare the evidence. If surprised: “That gives us something useful to test.”

**Guided discussion, about 8 minutes. Brad:** “What would you test before asking someone to rely on this all day?” Wesley connects answers to lighting, missed detections, timing, and the operator's evidence. A model score is not automatically a calibrated probability. A timing estimate does not independently establish physical position.

**Exit, about 2 minutes. Brad:** “You have seen a small version of the problem: make something work, change the conditions, and find out what still needs attention. Wesley, this is where your point about reliability comes in.” Return to slide 12 by 0:36.

**Recovery:** Show the camera view and last successful result. Ask what the audience would inspect first. Move on within two minutes. Barcodes, extra features, sentiment, and REMI are not required in this default block.

## 12. The hard problems — Brad → Wesley → Brad

**Cue:** Reliability is what lets the work leave our hands.

**Brad:** “Wesley, what are the hardest problems in getting these systems to work reliably on the floor?”

**Wesley:** “Some of the hardest problems in any system are the little things. Is the machine timed correctly? Is it getting the right signal at the moment it needs it? Or is something downstream causing an issue?”

“Then you have changing conditions. Something as simple as sunlight coming through a window could blind your cameras for thirty minutes.”

“You have to work through those issues so the whole system keeps working as conditions change. It needs to be reliable enough to leave your hands, and the people using it need confidence that it will keep doing its job.”

“Building that reliability and confidence takes work.”

**Brad:** “That is the difference between something we can demonstrate ourselves and something other people can rely on.”

## 13. Your starting point could look different — Brad

**Cue:** Mechanical, controls, software, testing. Invite people who are still learning.

**Brad:** “I started as a mechanical engineering intern who did not know how to do this. Wesley came in through software and machine prototyping. The work needs mechanical engineering, controls, software, and testing.”

“Tell us what you have built, what you are trying to learn, and what problem you want to take on. Your starting point may look different from ours.”

## 14. Let us connect — Brad → Wesley → Brad

**Cue:** Close the story before the two QR slides. Finish by about 0:40.

**Brad:** “Reach us at **awhite@tkghunt.com**. We'll be here afterward. Wesley, anything you'd like to add?”

**Wesley:** “Yeah, if you guys have any engineering questions or want to hear more about my internship experience, come talk with us afterward. I’d love to hear what you’re building and spitball some ideas with you.”

**Brad:** “We started with a rough OCR application, a problem we could not solve yet, and a chance to try. I called Wesley, and we got to build from there. The generations before us built the foundation. We want to build what the next generation can stand on.”

“Our history was made on the factory floor. The future will be, too. Come build and fight with us. Turn AI into action.”

**Bridge:** “Before we finish, here are two ways to keep exploring.”

## 15. Explore 4Founders — Brad

**Cue:** Homepage QR. This is not the interactive lab link. About 1 minute.

**Brad:** “This code takes you to the 4Founders home page: **4founders.dev**. You can open it now or save it for later.”

Give the room a moment to scan. The QR encodes **https://4founders.dev/**. Do not describe unverified homepage features. The next slide is the separate event activity.

**Bridge:** “The last slide takes you straight to the interactive demo.”

## 16. Try it yourself — Brad + Wesley

**Cue:** Final slide. Interactive lab QR, URL, and PIN stay visible through questions. 0:41–0:49 activity.

**Brad:** “Scan this code for the interactive demo, or open **4founders.dev/demo/ai-in-action/**. Enter PIN **877262**. Try the Audience Lab and notice what matches or surprises your expectations.”

Give **4–5 minutes**. Wesley helps with access. Brad keeps the final slide visible, then takes **two or three observations**: “What would you change before people used this every day?”

**Brad:** “We have time for questions. What are you curious about, or what are you trying to build?” Hold this final slide through 1:00 so the QR and PIN remain available.

**Access fallback:** Show one prepared example and ask for a prediction. Recheck the live URL, PIN, and projector scan before the event. The QR destination is verified in the file; service access still needs the event check.

## Source and status notes

Brad supplied the internship/OCR story, full-time school in Fayetteville, Friday–Monday work in Lonoke, inspection frustration, Keyence/Cognex experience, new CSG management approval, and call to Wesley in this chat on October 22, 2026. The script presents these as his personal experience, without adding dates, results, or performance comparisons. Wesley's supplied introduction, ownership remarks, real-reject moment, reliability remarks, and invitation are retained; additional story prompts remain his to fill.

Technical capabilities follow the existing project documentation: RemingtonVision for capture/labeling/YOLOX training and inference; Public Sentiment for VADER/domain scoring and source review; Little Chef README and docs/KNOWLEDGE.md for retrieval, citations, and scoped tools. The [bottle demo README](https://github.com/YeChamo/part-tracking-demo-ualr/blob/main/README.md) distinguishes documented modes. No production settings, inspection criteria, accuracy metrics, or private architecture have been added.

The historical OCR/SCADA anecdote is part of Brad's origin story; a standalone SCADA project slide remains removed. Sentiment and REMI live inserts remain optional and separate. The homepage QR and lab QR have distinct destinations. This revision does not establish hardware or venue readiness.
