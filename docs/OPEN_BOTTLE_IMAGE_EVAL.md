# Open bottle image check — 2026-10-22

The default demo uses the bundled **generic YOLOX-S bottle detector**, an exposed-drink color measurement, and an orange-cap inspection. It does not have Gatorade-specific detector weights. This small, manually selected set checks behavior across scenes; it is not an estimate of field accuracy. The external photographs are not in the repository.

Run the same inspection path used by the live demo against local images:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_bottle_images.py data\external_eval
```

| Photo and scene | Visible subject | Detected | Color | Cap | Note |
| --- | --- | ---: | --- | --- | --- |
| [Kitchen, top down](https://2.bp.blogspot.com/-qhJLK6QW1bo/V_ZV8wLTiiI/AAAAAAAALLo/nO_tLZSNKgsmzIRm74BqLN6_ZNuTTlfVACLcB/s1600/DSC05271.JPG) | Open disposable bottle, orange tamper band | 1 | yellow | missing | Body is partly clipped. |
| [Home Tester Club, desk](https://www.hometesterclub.com/ca/en/reviews/gatorade-g-zero-cool-blue-sports-drink-710ml) | Open Gatorade Zero bottle, lid beside it | 1 | blue | missing | OCR also read `GATORADE`, `ZERO`, and `COOL BLUE`. |
| [Pictureline, studio](https://www.pictureline.com/blogs/tutorials/josh-ross-and-his-gatorade-sculpture) | Open orange bottle with cap floating beside it | 1 | orange | missing | Dark background and splash. |
| [Fossil Forum, outdoor rocks](https://www.thefossilforum.com/topic/77225-hell-creek-coprolites/) | Capped orange bottle | 1 | orange | present | Capped control. |
| [MacRumors, desk](https://www.macrumors.com/2011/06/22/iphone-5-to-have-a-dual-led-flash/) | Capped empty older bottle | 2 | orange, green | present, missing | Duplicate inner box; the green/missing reading is wrong. |
| [Merca20, football turf](https://www.merca20.com/super-bowl-lviii-que-color-sera-el-gatorade-para-banar-al-coach/) | Capped orange bottle, small in scene | 0 | — | — | Missed detection. |
| [Unsplash, concrete](https://unsplash.com/photos/a-bottle-of-water-sitting-on-the-ground-fUwYgYirE3k) | Capped empty bottle lying sideways | 0 | — | — | Missed detection; orientation differs from conveyor view. |
| [eBay, counter](https://www.ebay.com/itm/186677078095) | Open opaque reusable Gatorade squeeze bottle | 0 | — | — | Different bottle category; no result. |
| [Dick's review](https://www.dickssportinggoods.com/p/gatorade-gx-30-ozstainless-steel-bottle-22gatugtrd30zgxbthyd/22gatugtrd30zgxbthyd) | Open stainless Gatorade bottle, top down | 0 | — | — | Different bottle category; no result. |

All three detected, open disposable bottles returned `missing`, with visually matching drink colors. The local live yellow bottle with its orange tamper band also returned `missing`. Across the 13 supplied example photos, all measured drink colors remained correct; cap readings were 8 `present` and 5 `unknown` where the top was clipped. Cap status remains informational and never changes the color sorting command.

The first pass called the kitchen bottle's cap `present` and the studio bottle `unknown`. Narrowing the orange mask to the plastic's hue range and recognizing a thin lower tamper band changed these to `missing` without changing the supplied capped examples. The MacRumors duplicate and the missed small/sideways bottles show where detector training or a better camera composition will matter more than cap thresholds. Label text is opportunistic: it was readable on the Home Tester Club image, but the other open views did not produce a reliable product name.

For the next live trial, collect varied *capped and uncapped disposable bottles* under the actual cameras, with labels facing toward and away from each view, glare, shadows, and bottle sizes at both near and far belt positions. Save examples that fail, especially duplicate boxes and missed bottles, before considering a Gatorade-specific detector fine tune.
