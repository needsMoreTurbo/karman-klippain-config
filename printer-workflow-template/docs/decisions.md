# Decision log

Why things are the way they are. Config comments say *what*; this says **why**, and what was tried
and rejected — so a later session (human or agent) doesn't "fix" something that is deliberate, or
re-litigate a settled tradeoff.

**Add an entry when:** a value is counter-intuitive, an obvious-looking alternative was rejected,
a default was overridden, or a bug cost real debugging time.

**Newest first. Keep entries short. Link the file, don't duplicate it.**

The single most valuable kind of entry is *"this looks wrong and isn't"* — because that is exactly
what a future session will try to correct.

---

<!-- Entry format — copy this shape:

## YYYY-MM-DD — Short title stating the decision or the bug
**Decision:** what is now true, concretely (the setting, the value, the file).
**Why:** the reasoning, including the mechanism if a bug was involved.
**Rejected:** the obvious alternative and why it doesn't work here.
**Evidence:** how it was confirmed — measured, tested on hardware, reproduced offline.

Not every entry needs all four lines, but "Why" is mandatory.
-->

_No entries yet. The first one usually arrives during `/setup`, when the maintainer explains why
something is set the way it is — capture those; they surface naturally in conversation and are
lost just as easily._
