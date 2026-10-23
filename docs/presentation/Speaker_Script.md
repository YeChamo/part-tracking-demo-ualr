# Engineering at The Kinetic Group — speaker script

**Brad Daugherty + Wesley Siharath · Go 4th Fridays · October 23, 2026**

16 slides. Brad advances slides and watches the clock. Wesley's introduction, personal story, reliability remarks, and closing use his supplied wording. Speak the quoted paragraphs; the other lines are cues and demo instructions.

## One-hour route

| Clock | Slides | Focus |
| --- | --- | --- |
| 0:00–0:05 | 1–5 | People, manufacturing context, and engineering method |
| 0:05–0:10 | 6–9 | Two inspection systems, sentiment, and Remi |
| 0:10–0:12 | 10 | Wesley's experience and ownership |
| 0:12–0:32 | 11 | Bottle demo and guided engineering questions |
| 0:32–0:35 | 12–13 | Reliability and invitation |
| 0:35–0:43 | 14 | Audience activity |
| 0:43–0:44 | 15–16 | Ideas, contact, and close |
| 0:44–1:00 | 16 held | Open questions |

These are clock targets, not a requirement to fill every minute. The prepared talk has about 16 minutes available, with 20 minutes for the demo, 8 for the activity, and 16 for questions. If a section finishes early, move forward.

**Story:** Remington's people built the foundation. Wesley entered through software and machine prototypes. Our work connects models and software to machinery and to the people using the result. Seeing a real reject handled is the payoff. Reliability is what lets that work leave our hands.

## 1. Engineering at The Kinetic Group — Brad → Wesley → Brad

**Cue:** Introductions, internship, and work reaching the floor.

**Brad:** “I am Brad Daugherty. I am an electrical engineer at Remington. I work mostly at the Lonoke site but do support projects across our organization. I’m here with Wesley Siharath, who helped start our Remington Vision work. Wesley, tell everyone a little about yourself and how you got started here.”

**Wesley:** “Hi, I’m Wesley Siharath. I’m an engineer here at Remington. I got started as an intern focused on software, with some prototyping on machines.”

“I came on full time this February, and now I work on AI tools and machines. One of the things that drew me here was being able to build a solution and see it put to use on the floor.”

**Brad:** “That is the story we want to show: how software becomes something useful on the floor, and what it takes to keep it working.”

## 2. Writing the next rules — Brad

**Cue:** 1816, Lonoke 1969, and our turn to contribute.

**Brad:** “Remington's history goes back to 1816. Lonoke has been part of it since 1969. We inherited generations of work in machinery and manufacturing. Our contribution is to connect that experience with cameras, controls, and software. Remington is one of five TKG ammunition brands, so the problems we support extend beyond one site.”

## 3. The stakes are real — Brad

**Cue:** Real machinery, real operators, real consequences.

**Brad:** “We work around energetic materials and moving machinery. That makes timing, clear information, and recovery part of the engineering problem. We build with operators, maintenance, quality, and safety. The software has to fit their workflow and the established safeguards.”

## 4. Engineering that reaches the floor — Brad

**Cue:** Capture, inference, decision, response.

**Brad:** “Sense, decide, act. For a vision system, that means acquiring an image, running inference, interpreting the output, and delivering a result in time for the workflow. A model result is one step in that chain. Camera conditions, signals, software latency, and the response all have to fit together. We test the whole chain and show people the evidence behind the result.”

## 5. The work spans the organization — Brad

**Cue:** Two live inspection systems, two broader capabilities. Finish by 0:05.

**Brad:** “Centerfire and shotshell inspection are live and still being refined. Public sentiment and Remi apply software to different questions: what customers are saying, and how engineers find project knowledge. The common problem is making the evidence useful to someone making a decision.”

## 6. Centerfire inspection — Brad → Wesley → Brad

**Cue:** Vision pipeline, visible evidence, operator trust.

**Brad:** “Remington Vision brings image capture, labeling, model training, and inference into one toolset. It uses YOLOX detection models and supports workstation and edge deployment. The model is only part of the system. The result has to reach a usable workflow, and people need to understand what the camera saw.”

**Wesley:** “On the floor we show operators what the system sees, listen when something is confusing, and make changes they can judge for themselves.”

**Brad:** “That feedback is part of commissioning and continued improvement. It is how the technical result earns trust.”

## 7. Shotshell inspection — Wesley → Brad

**Cue:** A different product changes the image and the data.

**Wesley:** “A different product creates a different visual problem. We have to check the camera view, the examples used to train and test the model, and how the result fits the line. We carry the tooling forward, then validate the application in its own conditions.”

**Brad:** “This is also live and being refined. Reusing software still leaves real integration work.”

## 8. Public sentiment — Brad

**Cue:** Collect, score, retain the source.

**Brad:** “The sentiment project collects public discussion, scores sentiment and product themes, and stores the results for review. The scoring uses VADER with a domain vocabulary. A trend gives the team somewhere to investigate. Keeping the original comments available lets people check what the score actually represents.”

## 9. Remi — Wesley → Brad

**Cue:** Retrieve project material, generate an answer, check the source.

**Wesley:** “Remi uses a local language model with retrieval over approved project documents. It indexes the material, finds relevant passages, and answers with citations. Scoped tools let it work within a defined workspace. The engineer still checks the source and the result.”

**Brad:** “Here the integration problem is keeping the answer connected to evidence and controlling what the tools can do.”

## 10. Why we love this work — Brad → Wesley → Brad

**Cue:** Variety, freedom, ownership, and a real result. Demo at 0:12.

**Brad:** “Wesley, what do you enjoy most about working here?”

**Wesley:** “What I love most is the variety of problems we face day to day. One day I might be debugging code in the office. Another day I might be knee-deep in grease, figuring out why a machine’s motor isn’t spinning.”

“I also enjoy the freedom to spitball an idea, explore different solutions, and take ownership of how we tackle the problem.”

“One moment that really stuck with me was seeing a real reject come through and watching our system toss it out. Seeing something I helped build actually do its job was an amazing feeling.”

“Following ideas through and seeing people get invested feels like helping pave the way for Remington. I enjoy figuring it out.”

**Brad:** “Let's show that connection between an image, a decision, and a visible result.”

## 11. Live demonstration — Brad + Wesley

**Cue:** Detection, color prediction, track, decision, one variation. 0:12–0:32.

**Before the event:** Rehearse the exact application build, camera, two bottles, and one variation. The repository's standard mode uses YOLOX bottle detection and a trained color model. The generic bundled bottle locator does not predict colors. Describe the mode actually shown. Keep the core demonstration on screen; include physical movement only if the complete event setup has been validated.

**Opening, 2 minutes. Brad:** “This is a separate event demo using Gatorade bottles. We detect the bottle, associate evidence with its track, and apply a color rule to produce an on-screen sort decision. First, predict the result. Then we will change one condition and look at what happened.”

**Baseline, 4 minutes. Brad** states the pass color and asks for predictions for two contrasting bottles. **Wesley** points out the bottle box, model color prediction, track, and displayed decision. In the standard repository mode, unknown color diverts. Show what this build actually did.

**Variation, 4 minutes.** Change one pretested orientation or position. Ask for a prediction. Compare the evidence with the baseline. If the result is surprising: “That gives us something useful to test.”

**Engineering discussion, 8 minutes. Brad:** “What would you test before relying on this all day?” **Wesley** connects answers to lighting, missed detections, timing, and the information an operator needs. If confidence comes up, explain that the model score is not automatically a calibrated probability. If physical timing comes up, explain that the demo estimates arrival from distance and measured speed; it does not independently measure physical actuator position.

**Transition, 2 minutes. Brad:** “The image, model, tracking, and response each have to hold up. Wesley's experience on the floor is where those requirements become concrete.” Return to slide 12 by 0:32.

**Recovery:** Show the camera view and last successful result. Ask what the audience would inspect first. Move on within two minutes. Optional barcodes and physical motion are outside the core sequence.

## 12. The hard problems — Brad → Wesley → Brad

**Cue:** Timing, signals, sunlight, and confidence.

**Brad:** “Wesley, what are the hardest problems in getting these systems to work reliably on the floor?”

**Wesley:** “Some of the hardest problems in any system are the little things. Is the machine timed correctly? Is it getting the right signal at the moment it needs it? Or is something downstream causing an issue?”

“Then you have changing conditions. Something as simple as sunlight coming through a window could blind your cameras for thirty minutes.”

“You have to work through those issues so the whole system keeps working as conditions change. It needs to be reliable enough to leave your hands, and the people using it need confidence that it will keep doing its job.”

“Building that reliability and confidence takes work.”

**Brad:** “That is the step from a prototype we operate ourselves to a system other people can rely on.”

## 13. Come fight for what is next — Brad

**Cue:** Mechanical, controls, software, and testing. Activity at 0:35.

**Brad:** “These problems cross mechanical engineering, controls, software, and testing. We want people who will follow a problem from the first question through deployment and improvement. Tell us what you have built and what you want to take on next.”

## 14. 4Founders challenge — Brad + Wesley

**Cue:** Scan, PIN, try, share. 0:35–0:43.

**Brad:** “Scan the QR code or open the URL on screen. Enter PIN **877262**. Try the Audience Lab and notice what matches or surprises your expectations.”

Give **4–5 minutes**. Wesley helps with access. Brad keeps the QR and PIN visible, then takes **two or three observations**. Ask: “What would you change before people used this every day?”

**Backup URL:** [4founders.dev/demo/ai-in-action/](https://4founders.dev/demo/ai-in-action/). Recheck access and scan before the event. If access fails, show one prepared example and ask the room to predict it.

## 15. Bring us your idea — Brad

**Cue:** Problem, affected person, first experiment.

**Brad:** “Your idea may go beyond the projects we showed. Tell us the problem, who it affects, and what you want to try. If there is a fit, let us explore it together.”

## 16. Let us connect — Brad → Wesley → Brad

**Cue:** awhite@tkghunt.com, questions, internship, and ideas. Hold for questions at 0:44.

**Brad:** “Reach us at **awhite@tkghunt.com**. We’ll be here afterward if anyone wants to connect. Wesley, anything you’d like to add?”

**Wesley:** “Yeah, if you guys have any engineering questions or want to hear more about my internship experience, come talk with us afterward. I’d love to hear what you’re building and spitball some ideas with you.”

**Brad:** “The generations before us built the foundation. We want to build what the next generation can stand on. Our history was made on the factory floor. The future will be, too. Come build and fight with us. Turn AI into action.”

## Source and status notes

The supplied deck and Brad's project descriptions establish the company context and that the two inspection systems are live and still being refined. Remington's [company history](https://www.remington.com/about-us.html) and [employee history](https://www.remington.com/big-green-blog/labor-day-special.html) are the existing sources for the 1816 origin and 1969 Lonoke start.

Technical descriptions were checked against the supplied local project documentation: RemingtonVision README (capture, labeling, YOLOX training/inference, and deployment options); Public Sentiment README (collection, VADER/domain scoring, storage, and dashboard); Little Chef README and docs/KNOWLEDGE.md (local model, retrieval, citations, and scoped tools). These describe software capabilities, not a claim that every feature is deployed on every production line. No inspection criteria, process settings, performance metrics, or production architecture have been added.

The bottle demo description follows the [repository README](https://github.com/YeChamo/part-tracking-demo-ualr/blob/main/README.md). This revision does not establish live hardware, camera, or venue readiness. Wesley supplied his four personal sections; his wording is retained.
