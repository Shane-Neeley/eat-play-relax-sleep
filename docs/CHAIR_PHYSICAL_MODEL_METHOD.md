# Physical-contact resonator method

The daily EPRS production on 2026-09-02 used a deterministic, source-free
physical-contact renderer for *The Chair Keeps Time*. Four role-specific
inharmonic resonator banks represent palm/body, wood/knuckle, heel/low-body,
and air/room contacts. Seeded excitation envelopes, short early reflections,
and role-specific decay make the parts remain distinct while they share a
7/4 floor grouped 2+2+3.

The method was informed by public timing and resonator documentation, then
implemented independently in song-local NumPy source. A finite Sonic Pi ring
contact sketch was retained as a comparison experiment, not used in the final
audio. The visual route is likewise deterministic Pillow drawing plus FFmpeg:
a fictional diagonal chair and cropped neutral gestures, with no faces,
external media, stock assets, readable interface, or generative model.

This method is a repeatable synthesis and editing technique, not evidence that
the output is a recording of a real chair or performer. Future EPRS work could
promote it into a `physical-contact` renderer contract that emits role
timelines, resonator settings, reflection taps, and paired visual gestures in
one verifiable manifest.
