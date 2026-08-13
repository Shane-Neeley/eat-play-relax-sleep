# EPRS — Amen Prism Surgery v1
#
# Musical idea: one familiar break is treated as raw geometry rather than a
# loop. Fixed slices establish a fingerprint, onset detection dismembers it,
# reverse fragments answer the snare, and a controllable slicer FX tightens the
# final section. This demonstrates sample surgery without external media.

use_bpm 168
use_random_seed 1681601
set_volume! 0.55

slices = (ring 0, 5, 2, 11, 7, 3, 14, 9, 1, 12, 6, 15, 4, 10, 8, 13)
rates = (ring 1, 1, 0.5, -1, 1.5, 1, -0.5, 1)
roots = (ring :e1, :g1, :d1, :bb0)

with_fx :reverb, room: 0.32, mix: 0.08 do
  with_fx :slicer, phase: 0.25, wave: 1, mix: 0 do |gate|
    24.times do |bar|
      section = if bar < 4
                  :fingerprint
                elsif bar < 12
                  :prism
                elsif bar < 16
                  :onset_vacuum
                else
                  :shatter
                end

      cue section if [0, 4, 12, 16].include?(bar)
      control gate,
        mix: (section == :shatter ? 0.42 : 0),
        phase: (bar >= 20 ? 0.125 : 0.25)

      16.times do |step|
        if section == :fingerprint && [0, 6, 10].include?(step)
          sample :loop_amen,
            slice: slices[step],
            num_slices: 16,
            sustain: 0,
            release: 0.075,
            lpf: 92,
            amp: 0.36
        elsif section == :onset_vacuum && [0, 3, 9, 14].include?(step)
          sample :loop_amen,
            onset: (bar * 3 + step),
            sustain: 0,
            release: (step == 14 ? 0.16 : 0.065),
            rate: rates[bar + step],
            pan: -0.55 + step / 15.0,
            amp: 0.34
        elsif section != :fingerprint && (spread(section == :shatter ? 11 : 7, 16).rotate(bar))[step]
          sample :loop_amen,
            slice: slices[step + bar],
            num_slices: 16,
            sustain: 0,
            release: (section == :shatter ? 0.045 : 0.075),
            rate: rates[step + bar],
            lpf: 84 + (step % 5) * 7,
            pan: (step.even? ? -0.28 : 0.28),
            amp: 0.29
        end

        if step.zero? || (section == :shatter && [5, 11].include?(step))
          sample :bd_haus, amp: (step.zero? ? 0.56 : 0.34), cutoff: 90
        end

        if [0, 7, 13].include?(step) && section != :fingerprint
          use_synth :subpulse
          play roots[bar] + (step == 13 ? 7 : 0),
            release: 0.11,
            cutoff: (section == :shatter ? 94 : 72),
            amp: 0.34
        end

        sleep 0.25
      end
    end
  end
end
