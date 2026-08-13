# EPRS — Neon Bone Machine v1
#
# Musical idea: footwork speed on the surface, half-time weight underneath.
# The same four-note DNA is squeezed through false starts, a vacuum section,
# displaced kick swarms, and a final bar that folds the hook inside out.
#
# Finite and deterministic: 32 bars at 174 BPM, built-in sounds only.

use_bpm 174
use_random_seed 174404
set_volume! 0.57

roots = (ring :f1, :eb1, :b0, :db1)
hook = (ring 0, 7, 3, 10, 0, 12, 7, 15)

with_fx :reverb, room: 0.28, mix: 0.08 do
  with_fx :distortion, distort: 0.12, mix: 0.09 do
    32.times do |bar|
      section = if bar < 4
                  :false_start
                elsif bar < 12
                  :sprint
                elsif bar < 16
                  :vacuum
                elsif bar < 24
                  :mutation
                else
                  :bone_machine
                end

      cue section if [0, 4, 12, 16, 24].include?(bar)

      kick_steps = case section
                   when :false_start then (bar == 3 ? [0, 7, 14] : [0, 10])
                   when :sprint then [0, 3, 6, 10, 13]
                   when :vacuum then (bar.even? ? [0] : [11, 14])
                   when :mutation then [0, 2, 5, 9, 10, 14]
                   else [0, 2, 3, 6, 9, 10, 12, 15]
                   end

      snare_steps = case section
                    when :false_start then (bar == 3 ? [15] : [])
                    when :vacuum then [12]
                    else [4, 12]
                    end

      16.times do |step|
        if kick_steps.include?(step)
          sample :bd_haus,
            amp: (step.zero? ? 0.70 : 0.48),
            rate: (section == :bone_machine && step.odd? ? 1.34 : 1.0),
            cutoff: (section == :vacuum ? 78 : 112)
        end

        if snare_steps.include?(step)
          sample :sn_dub,
            amp: (step == 12 ? 0.47 : 0.32),
            rate: (bar % 4 == 3 ? 1.42 : 0.96),
            pan: (step == 4 ? -0.12 : 0.12)
        end

        if section != :vacuum && (step.even? || section == :bone_machine)
          sample :drum_cymbal_closed,
            amp: (step % 4 == 0 ? 0.15 : 0.065),
            finish: 0.035 + (step % 3) * 0.012,
            rate: (section == :mutation ? 1.55 : 1.08),
            pan: -0.55 + step / 15.0
        end

        if [7, 15].include?(step) && [:sprint, :mutation, :bone_machine].include?(section)
          sample :elec_blip2,
            amp: 0.13,
            rate: 0.52 + (bar % 5) * 0.24,
            pan: (step == 7 ? 0.52 : -0.52)
        end

        if [0, 6, 11, 14].include?(step) && section != :false_start
          use_synth :subpulse
          note_offset = hook[(bar + step) % hook.length]
          play roots[bar] + note_offset,
            release: (section == :vacuum ? 0.32 : 0.10),
            cutoff: (section == :bone_machine ? 101 : 78),
            amp: (step.zero? ? 0.42 : 0.29)
        end

        if section == :mutation && [1, 5, 8, 13].include?(step)
          use_synth :tb303
          play roots[bar] + 24 + hook[step % hook.length] + (bar % 2) * 0.37,
            release: 0.055,
            cutoff: 82 + (bar % 8) * 5,
            res: 0.72,
            wave: 1,
            amp: 0.13,
            pan: (step.even? ? -0.3 : 0.3)
        end

        if section == :bone_machine && [3, 7, 11, 15].include?(step)
          use_synth :blade
          play roots[bar] + 36 + hook[(step + bar) % hook.length],
            release: 0.045,
            cutoff: 118,
            amp: (bar >= 30 ? 0.16 : 0.10),
            pan: (step < 8 ? -0.42 : 0.42)
        end

        if bar == 31 && step >= 12
          sample :drum_tom_hi_hard,
            amp: 0.23 + (step - 12) * 0.035,
            rate: 0.7 + (step - 12) * 0.22,
            pan: -0.6 + (step - 12) * 0.4
        end

        sleep 0.25
      end
    end
  end
end
