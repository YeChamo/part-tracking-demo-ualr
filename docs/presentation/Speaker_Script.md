# Engineering at The Kinetic Group — practice script

**Brad Daugherty + Wesley Siharath · Go 4th Fridays · October 23, 2026**  
Matches the 17-slide corporate deck. Practice the thought and handoff on each slide; speak naturally. Wesley owns his introduction, examples, and phrasing.

## The one-hour plan

| Clock | Slides | Purpose |
| --- | --- | --- |
| 0:00–0:06 | 1–5 | Introduce us, the company, the plant, and our work |
| 0:06–0:14 | 6–10 | Five project stories |
| 0:14–0:16 | 11 | Why we love the work |
| 0:16–0:36 | 12 | Live bottle demo, predictions, and questions |
| 0:36–0:39 | 13–14 | Hard problems and invitation to join |
| 0:39–0:47 | 15 | 4Founders audience activity |
| 0:47–0:48 | 16–17 | Ideas, contact, and close |
| 0:48–1:00 | 17 held | Open questions |

This gives roughly **20 minutes of prepared speaking**, **20 minutes of live demo**, **8 minutes for the activity**, and **12 minutes of open questions**. Brad advances slides and watches the clock. Wesley can add his own story where it helps the audience.

## The message to return to

> Remington's history was built by people solving difficult manufacturing problems. Today we are building systems that help people make better decisions in real production. We want Remington and The Kinetic Group to keep writing the rules for manufacturing in the decades ahead, and we want others to help us do it.

**Company map:** The Kinetic Group is the broader ammunition organization; Remington is one of its five brands. Brad's teams work across TKG and mainly at Remington in Lonoke. The three floor examples are live and still being polished. Public sentiment and Remi show the wider range of engineering work; do not describe them as production-line deployments.

## 1. Engineering at The Kinetic Group — Brad → Wesley → Brad

**Brad:** “Good afternoon. I'm Brad Daugherty. I lead small engineering teams across The Kinetic Group, and most of my work is at Remington in Lonoke. I'm here with Wesley Siharath. Wesley helped start our Remington Vision work, beginning as one of our first software interns and carrying it into his engineering role. Wesley, introduce yourself however you'd like.”

**Wesley:** Introduce yourself in your own words. Give the room your path from intern to engineer and what you work on now.

**Brad:** “We want to show you what this work looks like at a real ammunition plant, let you see a live system in action, and talk about the people we hope will join us. First, why this place matters.”

## 2. Writing the next rules — Brad

“Remington's story reaches back to 1816. Lonoke has been part of that manufacturing story since 1969. That history was made by people who understood materials, machinery, quality, and how to make things at scale. We respect the foundation they built.”

“Today the world has changed. Cameras, controls, software, and local computing give us new ways to understand production while it is happening. We have the chance to build new capabilities on top of that foundation. We want Remington and The Kinetic Group to continue writing the rules for manufacturing for decades to come.”

“The Kinetic Group includes Remington alongside Federal, CCI, Speer, and HEVI-Shot. That gives us a field of engineering problems bigger than one plant or product. Today's examples come mainly from Remington in Arkansas, while the ambition spans the organization.”

**Bridge:** “That ambition has to stand up in a serious operating environment.”

## 3. The stakes are real — Brad

“This is an ammunition plant. People work around propellants, primers, energetic materials, and moving machinery. Decisions here affect real operators and real production. We build with the people who will use a system: operators, quality, maintenance, engineering, and safety.”

“A promising prototype is a start. The real test is whether information is timely, understandable, and useful on the floor. Our software supports the operation; qualified people and established safeguards remain essential.”

## 4. Engineering that reaches the floor — Brad

“Sense, decide, act. We capture a machine signal or camera image. Software turns it into something useful. A person or equipment responds through the right workflow.”

“The three words are simple. Making them reliable together is the engineering challenge. Was the signal trustworthy? Did the result arrive in time? Can someone understand what to do? Those questions shape the work.”

## 5. The work spans the organization — Brad

“On the left are three systems live in production at Remington and being refined: SCADA, centerfire inspection, and shotshell inspection. Each helps people understand or respond to what is happening on the floor. On the right are broader capabilities. Public sentiment helps teams hear customers in their own words. Remi helps engineers work with project knowledge.”

“They are different applications, but the principle is the same: a system should help someone make a better decision. Sometimes that person is an operator watching a line. Sometimes it is an engineer checking the source behind an answer. We will give you the purpose and one challenge for each project. Save us the deep technical questions for the demo or afterward.”

## 6. SCADA — Brad

“SCADA gives us shared visibility into machine and process signals. Think of two questions: what is happening now, and what changed? A signal alone can be hard to interpret. With time and context in a production history, operators and engineers can investigate from the same record.”

“The interesting work is deciding which signals matter and making the display useful to a person who has to act. A screen can look impressive but still fail to answer a floor question. This is live, and we are polishing it with the people who use it.”

**Optional 20-second story:** Name one public-safe question a shared history helped answer; describe the question and decision, not internal settings or process limits.

## 7. Centerfire inspection — Brad → Wesley → Brad

**Brad:** “Centerfire inspection is in the production flow. A camera captures a view, software evaluates it, and the result enters a workflow. That sounds like a computer vision problem. In practice, one of the hardest challenges is human: how do we earn the trust of the people who will rely on the result?”

**Wesley:** In your own words: “A promising result at a desk is just a start. On the floor we show operators what the system sees, listen when something is confusing, and make changes they can judge for themselves.” Add a brief example of working with a user if you have one you are comfortable sharing.

**Brad:** “Trust does not arrive the day a system is installed. It is built by showing evidence, listening, and improving the system in use. This inspection is live and still being polished.”

## 8. Shotshell inspection — Wesley → Brad

**Wesley:** “Shotshell inspection is a different visual problem. We cannot assume that a view or workflow designed for another product will fit. We have to understand the product, where a camera can see it, and how the result will be used on the line.” Add your own floor story when ready; this public-safe version is enough for now.

**Brad:** “It is also live and being refined. Together, the two inspection projects show that we are building an adaptable engineering capability, then fitting each system to its real production setting.”

## 9. Public sentiment — Brad

“Our work is not limited to the plant. The sentiment project helps product and business teams hear what people say publicly about products and brands. It groups discussion into themes and keeps the original sources available.”

“A graph can suggest that something changed; the actual comments tell you what people meant. The system gives a team a better starting question and a way to inspect the evidence.”

## 10. Remi — Wesley → Brad

**Wesley:** “Remi is our local language-model work for engineering. An engineer asks a question about a project, finds relevant material, and checks the proposed answer before using it. The engineering is the whole system around the model: the material it can use, the tools it can call, how it shows its source, and how a person verifies the result.”

**Brad:** “From production signals to engineering knowledge, we use technology where it helps someone act with more understanding. Wesley, why do you love this work?”

## 11. Why we love this work — Wesley

Tell this in your own voice. Your four points: **early software intern → AI and machines → freedom and ownership → unexpected growth.** A practice version:

“I started here as one of the first software interns and got involved in work with AI and different machines. What I enjoy most is the variety, the freedom to explore ideas, and the chance to take ownership. There is always something new to figure out, and I've had opportunities here that I wouldn't have expected coming in.”

Add one specific moment that feels like yours: a problem you owned, an experiment that changed direction, or something you learned from the floor. **Brad:** “That mix of ownership and real stakes is why we want more people here. Let us show you the system live.”

## 12. Live demonstration — Brad + Wesley, 20 minutes

**Opening (1 minute). Brad:** “We will demonstrate the same sense–decide–act pattern with something familiar: Gatorade bottles. This setup is for this event and is separate from the production inspection systems. Watch the camera view, the decision on screen, and what happens next.”

**Round 1 (4 minutes):** Brad places one bottle. Wesley narrates the camera view and on-screen classification or sorting decision. Brad asks what the system had to notice. Repeat once so the pattern is clear.

**Round 2 (5 minutes):** Wesley changes one visible condition or selects another bottle or feature. Brad asks the audience to predict the result before running it. Wesley explains what changed. If surprised, say: “That gives us something useful to test.”

**Engineering questions (5 minutes):** Ask: “If this had to work all day on a real line, what would you test next?” Take answers. Wesley discusses variation, timing, observability, and user feedback at a public-safe level. Brad connects the answers to reliability and trust.

**Optional feature (3 minutes):** Show one additional feature only if it adds a new lesson. Keep cause and result visible; avoid a feature tour.

**Transition (2 minutes). Brad:** “That was a controlled demonstration. In production, the hard part is keeping a useful result as conditions change, the line moves, and people depend on it.”

**If the demo stalls:** Show the camera view and last successful result. Ask the room what they would inspect first. Move on after two minutes instead of troubleshooting for the whole session.

## 13. The hard problems — Wesley → Brad

**Wesley:** “The challenge is not getting one good result. Conditions change. The result has to arrive at the right time. The person using it needs to know whether to trust it.” Connect one demo moment to a test you would run on a real system.

**Brad:** “These are among the most interesting engineering challenges we know. The technology matters, and so does making it useful to the people on the floor. That is how we earn the right to write the next rules.”

## 14. Come fight for what is next — Brad

“We are looking for people who want to work on this with us. Opportunities across Remington and The Kinetic Group span mechanical engineering, controls, software, testing, and the connections between them. There are problems on the floor, in our tools, and in how those tools reach people.”

“Tell us what you have built, what you want to learn, and what kind of problem you want to take on. Come help us write the rules for the next decades.”

## 15. 4Founders challenge — Brad, 8 minutes

“Now we want you to try something yourselves. Scan the QR code or open the URL on screen. Enter the event PIN, **877262**. The activity opens as **AI in Action — Audience Lab**. Notice where your expectation matches or differs from what happens.”

Give the room **4–5 minutes**. Wesley helps with access; Brad keeps this slide visible. Take **two or three observations**: “What surprised you?” or “What would you change if people had to use this every day?” Tie one answer to the trust theme.

**Backup:** [4founders.dev/demo/ai-in-action/](https://4founders.dev/demo/ai-in-action/) · PIN **877262**. The QR decoded to this URL and the PIN opened Audience Lab when checked on October 22, 2026. Recheck the service and projector scan on event day because event access can change.

## 16. Bring us your idea — Brad

“Your interests may go beyond the roles or projects we named. We still want to know what you want to pursue. If there is a fit, we would be interested in exploring it together. Tell us the problem you care about and what you would like to try.”

**Bridge:** “The first step is a conversation.”

## 17. Let us connect — Brad → Wesley → Brad

**Brad:** “Reach us at **awhite@tkghunt.com**. Put a few words in your note about what you want to build, work on, or ask. Wesley and I will be here afterward.”

**Wesley:** Invite questions and projects in your own words.

**Brad:** “Our history was made on the factory floor. The future will be, too. Come build and fight with us. Turn AI into action.” Hold this slide for open questions.

## Staying on track

- **0:06:** Reach the portfolio map. Shorten the history if behind.
- **0:16:** Start the live demo. Protect two clear outcomes and one audience prediction.
- **0:36:** Leave the demo. Save deep technical discussion for open questions.
- **0:39:** Open the activity. Keep QR and PIN visible until most people are in.
- **0:48:** Reach the contact slide and use the rest of the hour for questions.
- **Quiet room:** Ask “What would you need to trust a result like this on a factory floor?”
- **Short on time:** Give one sentence each on sentiment and Remi; preserve the plant context, demo, invitation, activity, and contact.

## Source and status notes

Remington's [company history](https://www.remington.com/about-us.html) supports the 1816 origin, TKG's five-brand structure, and Lonoke ammunition focus. Its [employee history](https://www.remington.com/big-green-blog/labor-day-special.html) supports the 1969 Lonoke start. Brad confirmed SCADA, centerfire inspection, and shotshell inspection are live and being polished. The Remington Systems Lab showcase narration informed the project descriptions. Wesley's shotshell story remains his to choose.
