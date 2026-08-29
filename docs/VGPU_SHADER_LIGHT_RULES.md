# vGPU shader light rules

EPRS completed a local portrait vGPU bake-off for **Tide Says Uh-Huh** on
2026-08-29. The same source-integrated track was rendered through five
different visual branches and reviewed in contact sheets at the target
presentation size.

## Bake-off result

1. **Liquid Glass** — SDF blob union, pixel-scale rim, bounded distortion,
   Fresnel-like edge energy, and narrow specular streaks.
2. Caustic Cipher — phase-shifted sine ridges, hard waterline, and bubble rings.
3. **Prism Beams** — crisp line fields, moving aperture, and separated light
   bands.
4. Particle Trails — compact orbital cores with directional tails.
5. Hard Light — flat planes, disc, bars, and narrow contours.

The review found **#1 Liquid Glass and #3 Prism Beams least blurry**. #5 was a
sharp clarity control but flatter; #2 retained ridge detail with more texture;
#4 was intentionally softer because of its tails. This is a local visual
review, not an audience-retention claim.

## Default production rule

Every future vGPU picture must use at least one authored advanced light
technique and must be auditioned at final delivery size. Preferred techniques
are:

- pixel-aware SDF rims, Fresnel-like edge energy, and narrow specular highlights;
- crisp line-SDF beams with a moving aperture;
- phase-shifted caustic ridges with a hard waterline;
- separated sharp particle cores and lower-energy directional trails; or
- hard-light planes and narrow contour stacks.

Keep anti-alias widths tied to output pixels and apply tone compression locally
to additive motifs. Broad bloom, large feathered rings, and unbounded additive
hotspots may be accents only; they cannot be the primary readability mechanism.
When two visual ideas are otherwise equal, prefer the #1/#3 clarity bar.

The full audition note and research provenance are preserved at
`songs/tide-says-uh-huh/notes/production/vgpu-shader-bakeoff-20260829.md` and
`songs/tide-says-uh-huh/notes/research/vgpu-shader-bakeoff-20260829.json`.
