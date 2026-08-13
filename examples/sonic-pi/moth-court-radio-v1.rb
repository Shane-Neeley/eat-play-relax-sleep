# EPRS — Moth Court Radio v1
#
# Musical idea: a very slow triplet broadcast from a flooded ballroom. The
# pulse is carried by sub thumps, clipped fragments of ambient samples, and a
# chord that slowly loses its tuning. Silence and long tails do as much work as
# the hits. This is a beat, but it behaves like a haunted weather system.
#
# Finite and deterministic: 20 bars of 4/4 triplets, built-in sounds only.

use_bpm 66
use_random_seed 660031
set_volume! 0.54

roots = (ring :a1, :f1, :c2, :eb2, :a1)
glass_rates = (ring 0.25, 0.333, -0.25, 0.5, -0.333)

with_fx :reverb, room: 0.92, mix: 0.34 do
  with_fx :echo, phase: 0.75, decay: 5.5, mix: 0.18 do
    20.times do |bar|
      root = roots[bar]
      section = if bar < 4
                  :signal
                elsif bar < 10
                  :court
                elsif bar < 14
                  :blackout
                else
                  :return
                end

      cue section if [0, 4, 10, 14].include?(bar)

      12.times do |triplet|
        downbeat = triplet == 0

        if downbeat && section != :blackout
          sample :bd_boom,
            amp: (bar < 4 ? 0.30 : 0.46),
            rate: (bar.even? ? 0.72 : 0.58),
            cutoff: 72
        end

        if section == :court && [5, 11].include?(triplet)
          sample :sn_dolf,
            amp: (triplet == 11 ? 0.27 : 0.18),
            rate: (bar % 3 == 0 ? 0.63 : 1.31),
            pan: (triplet == 5 ? -0.34 : 0.34)
        elsif section == :return && [4, 8, 11].include?(triplet)
          sample :perc_snap,
            amp: (triplet == 11 ? 0.22 : 0.11),
            rate: 0.78 + (bar % 4) * 0.17,
            pan: -0.5 + triplet / 11.0
        end

        # Tiny windows turn recognizable ambience into dusty percussion.
        if [2, 7].include?(triplet) && section != :blackout
          slice_start = triplet == 2 ? 0.08 : 0.61
          sample :ambi_glass_hum,
            start: slice_start,
            finish: slice_start + 0.025,
            rate: glass_rates[bar],
            amp: 0.18,
            pan: (triplet == 2 ? -0.62 : 0.62)
        end

        if section == :blackout && triplet == (bar % 3) * 4
          sample :ambi_lunar_land,
            start: 0.2,
            finish: 0.27,
            rate: (bar.even? ? -0.21 : 0.19),
            amp: 0.20,
            pan: (bar.even? ? -0.4 : 0.4)
        end

        if downbeat || (section == :return && triplet == 10)
          use_synth :dark_ambience
          tuning_drift = (bar - 10) * 0.07
          play root + tuning_drift,
            attack: 0.08,
            sustain: (section == :blackout ? 0.2 : 0.65),
            release: 2.1,
            cutoff: 58 + bar * 2,
            amp: (section == :blackout ? 0.11 : 0.20)
        end

        if [3, 9].include?(triplet) && [3, 7, 9, 14, 17, 19].include?(bar)
          use_synth :hollow
          play chord(root + 24, :minor7).choose + (bar % 2) * 0.31,
            attack: 0.01,
            release: 0.24,
            cutoff: 96,
            amp: 0.09,
            pan: (triplet == 3 ? 0.5 : -0.5)
        end

        sleep 1.0 / 3
      end
    end
  end
end
