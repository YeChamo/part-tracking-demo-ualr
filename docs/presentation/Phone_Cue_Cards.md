# Engineering at The Kinetic Group — phone cue cards

**Brad + Wesley · Friday, October 23, 2026 · 11:30 a.m. · 17 slides**

**The route:** Brad's struggle → CSG gives us a chance → Wesley joins → Remington's legacy → engineering on the floor → project examples → live demo → reliability → people we want to meet → two QR links.

**Purpose:** Bring AI into real work and help build the next generation of manufacturing.

**Clock:** Intro **0:00–0:06** (up to 0:08 is fine) · examples by **0:10** · demo at **0:16** · back to slides at **0:36** · closing by **0:40** · 4Founders homepage **0:40** · Audience Lab **0:41–0:49** · questions to **1:00**.

**Slide control:** Brad advances. Wesley runs the bottle app. When a card says **HOLD**, let the story continue on that slide. Slide 12 → demo app → return directly to slide 13.

---

## 1 · OUR BEGINNING — BRAD

**HOLD THE COVER. Tell the complete beginning before advancing.** About 3–5 minutes.

“I'm Brad Daugherty, an electrical engineer at Remington. Most of my work is in Lonoke, and I support projects across The Kinetic Group. Wesley Siharath is here with me.”

**Story ladder:** Mechanical engineering intern → full-time school in Fayetteville and full-time Lonoke work, Friday–Monday → OCR from HMI web servers → first AI app / “probably the worst SCADA system the world has ever seen” → pause for laugh → Keyence and Cognex inspection struggle → nearly a year, felt defeated → experienced engineers had struggled too.

**Finish:** “Eventually I couldn't keep approaching it the same way. I proposed that we build it ourselves.”

**ADVANCE TO 2 only after that sentence.**

## 2 · CSG, THE CHANCE, AND WESLEY — BRAD → WESLEY → BRAD

**HOLD SLIDE 2 through the full handoff and Wesley's story.** About 3–4 minutes.

**Brad:** “Before I tell you what happened to that proposal, here is where CSG fits.” Czechoslovak Group: Prague; origins in 1995; defense, aerospace, automotive. TKG is in CSG Ammo+; Remington is a TKG brand. **Then:** New CSG management approved building our own system. “Go get an intern.” I called Wesley. “Take it from here.”

**Wesley:** Introduce yourself. Intern in software and machine prototyping. **Eight at night, stacking boxes → interview notification → “Thank God, I might actually get to use this degree.”** Interesting projects; charged headfirst into something new. First problem: GPIO, Jetson patch, low-voltage output and a 24-volt relay. **Point:** Software had to work with a machine. Came on full time this February; now AI tools and machines.

**Brad:** “Our beginning is recent. The manufacturing history we are building on goes back much further.”

**ADVANCE TO 3 after “goes back much further.”**

## 3 · REMINGTON'S HISTORY — BRAD

**1816 → Lonoke 1969 → our contribution.**

“We inherited generations of manufacturing work. Our contribution is connecting that experience with cameras, controls, and software. Remington is one of five TKG ammunition brands, so the problems extend beyond one site.”

**Land:** “That history carries responsibility, because this is real manufacturing.”

**ADVANCE TO 4.**

## 4 · THE STAKES — BRAD

**Real machinery, real operators, real consequences.**

“Those inspection projects were challenging because we work around energetic materials and moving machinery. Timing, clear information, and recovery are part of the problem. We build with operators, maintenance, quality, and safety. Software must fit their workflow and established safeguards.”

**Ask:** “What does it take for software to reach that floor?”

**ADVANCE TO 5.**

## 5 · THE WHOLE SYSTEM — BRAD

**SENSE → DECIDE → ACT. Capture → inference → decision → response.**

“When we proposed building it ourselves, this was the whole problem. A model result is one step. Camera conditions, machine signals, latency, and the response all have to fit together. We test the entire chain and show people the evidence behind the result.”

**Land:** “You can see that pattern across our work.”

**ADVANCE TO 6.**

## 6 · MAP OF THE WORK — BRAD · AIM FOR 0:10

**Two live inspections. Two broader tools.**

“Centerfire and shotshell inspection are live and still being refined. Public sentiment asks what customers are saying. Remi helps engineers find project knowledge. Across all four, the goal is evidence someone can use to make a decision.”

**Next:** “Start with centerfire and what building that capability involves.”

**ADVANCE TO 7.**

## 7 · CENTERFIRE — BRAD → WESLEY → BRAD

**Build the vision pipeline; earn trust in the result.**

**Brad:** “Remington Vision connects image capture, labeling, model training, and inference. It uses YOLOX detection and can run on a workstation or at the edge. The result must reach a usable workflow, and people need to understand what the camera saw.”

**Wesley:** “On the floor we show operators what the system sees, listen when something is confusing, and make changes they can judge for themselves.”

**Brad:** “That feedback is how a technical result earns trust.”

**Handoff:** “A different product brings a different problem. Wesley, take shotshell.” **ADVANCE TO 8.**

## 8 · SHOTSHELL — WESLEY → BRAD

**A lot happens before model training.**

**Wesley:** “We first have to learn what the camera can see, collect useful examples, and label them consistently. On a different product, those questions return. We carry over software and learning, then get images and testing right for the new application.”

**Finish exactly:** “Every problem we figure out gives us a better starting point for the next one—and there's always something new to learn.” **Pause and look to Brad.**

**Brad:** “These are the problems we face on the floor.”

**ADVANCE TO 9 after Brad's line.**

## 9 · PUBLIC SENTIMENT — BRAD

**Collect → score → retain source.**

“Away from the production line, we collect public discussion and score sentiment and product themes with VADER and a domain vocabulary. The trend tells us where to investigate. The original comments let people check what the score represents.”

**Handoff:** “Public comments are one source. Our project documents are another. Wesley?” **ADVANCE TO 10.**

## 10 · REMI — WESLEY → BRAD

**Approved documents → relevant passages → answer with citations → engineer checks.**

**Wesley:** “Remi uses a local language model and retrieval over approved project documents. Scoped tools keep work inside a defined workspace. The engineer verifies the source and result.”

**Brad:** “The integration problem is keeping the answer tied to evidence and controlling what tools can do.”

**Next:** “The part that keeps us interested is carrying an idea into use.” **ADVANCE TO 11.**

## 11 · WHY WE LOVE IT — BRAD → WESLEY → BRAD · DEMO AT 0:16

**Brad:** “What do you enjoy most about actually doing this work here?”

**Wesley:** Variety: code one day, grease and a stopped motor the next. Freedom to spitball ideas and own solutions. **Real reject:** our system tossed out a reject; seeing it work was an amazing feeling. **Dented shell:** Brad called it his child and was happy for a week. **Pause for laugh.** Finish: following ideas through helps pave the way for Remington.

**Brad:** “Let's show the connection between an image, a decision, and a visible result.”

**ADVANCE TO 12, then hold it for the demo introduction.**

## 12 · LIVE BOTTLE DEMO — BRAD + WESLEY · 0:16–0:36

**Core route:** Two bottles → predictions → one pretested variation → engineering questions.

**Open, 2 min — Brad:** “This is a separate event demo. We detect a Gatorade bottle, associate evidence with its track, and apply a color rule to show an on-screen sort decision. Predict the result; then we will change one condition.”

**Switch to app:** “Wesley, let's look at it.” **Hold slide 12 until this line.**

**Baseline, 4 min — Both:** Brad states the pass color and asks for predictions on two contrasting bottles. Wesley points to bottle box → model color prediction → track → displayed decision. The standard build pairs YOLOX bottle detection with a trained color model; describe the actual build being shown. The generic bottle locator alone does not predict color. Show physical movement only if the complete setup was validated.

**Variation, 4 min — Both:** Change one pretested position or orientation. Ask for a prediction; compare evidence. If surprised: “That gives us something useful to test.”

**Discussion, 8 min — Brad asks:** “What would you test before relying on this all day?” Wesley connects answers to lighting, missed detections, timing, and what an operator needs to see. Model confidence is not automatically a calibrated probability.

**Exit, 2 min — Brad:** “Image, model, tracking, and response all have to hold up. Wesley's floor experience makes those requirements concrete.” **Return directly to slide 13 by 0:36.**

**If stalled:** Show the last successful result, ask what to inspect first, and move on within two minutes.

## 13 · HARD PROBLEMS — BRAD → WESLEY → BRAD

**Timing → signals → sunlight → confidence.**

**Brad:** “What are the hardest problems in getting a system to work reliably on the floor?”

**Wesley:** “Is the machine timed correctly? Is the right signal there when needed? Is a downstream issue involved? Sunlight can blind a camera for thirty minutes. The system has to keep working as conditions change, reliably enough to leave our hands.”

**Brad:** “That is the step from a prototype we operate ourselves to a system others can rely on.”

**Next:** “That work needs people with different skills.” **ADVANCE TO 14.**

## 14 · JOIN US — BRAD

**Mechanical + controls + software + testing.**

“I started as a mechanical intern trying to solve a problem I did not understand. Wesley came through software and machine prototyping. We need people from all of these directions who will follow a problem from its first question through deployment and improvement.”

**Ask:** “What have you built? What do you want to take on next?”

**Next:** “If that sounds like your kind of work, come talk to us.” **ADVANCE TO 15.**

## 15 · CONTACT AND CLOSE — BRAD → WESLEY → BRAD · ABOUT 0:40

**Contact first; finish the personal story before the QR slides.**

**Brad:** “Reach me at **bdaugherty@tkghunt.com**, and Wesley at **wsiharath@tkghunt.com**. We will be here afterward. Wesley, anything you'd like to add?”

**Wesley:** Invite engineering questions, internship questions, and ideas people are building. “Come talk and spitball ideas with us.”

**Brad:** Rough OCR app → unsolved inspection problem → chance to try → called Wesley. “You can begin while you're still learning, find people to build with, and keep working until the result is useful to someone else. Our history was made on the factory floor. The future will be, too. Come help us bring AI into real work and build the next generation of manufacturing.”

**Bridge:** “Before we finish, here are two ways to keep exploring.” **ADVANCE TO 16.**

## 16 · 4FOUNDERS HOME — BRAD · ABOUT 0:40–0:41

**Homepage QR: https://4founders.dev/**

“This code takes you to the 4Founders home page. You can open it now or save it for later.” **Pause for a scan.**

**Next:** “The last slide takes you straight to the interactive demo.” **ADVANCE TO 17.**

## 17 · AUDIENCE LAB — BRAD + WESLEY · 0:41–1:00

**Activity: scan → PIN → try → share.**

**Brad:** “Scan the QR or open [4founders.dev/demo/ai-in-action/](https://4founders.dev/demo/ai-in-action/). Enter **PIN 877262**. Try the Audience Lab and notice what matches or surprises your expectations.”

Give **4–5 minutes**. Wesley helps with access. Brad takes **two or three reactions:** “What would you change before people used this every day?”

**Questions, 0:49–1:00:** “What are you curious about, or what are you trying to build?” **HOLD SLIDE 17** so the QR, URL, and PIN remain visible.

**If access fails:** Show one prepared example and ask for predictions.

---

## If you lose the thread

**Brad:** Your learning → inspection struggle → chance → Wesley → Remington's history → real floor systems → invite people in.

**Wesley:** Your first machine problem → getting the next application's data right → real reject → reliability others can trust.

**If behind:** Keep the full personal close, two clear bottle outcomes, and both QR slides. Move from the demo at **0:36**.
