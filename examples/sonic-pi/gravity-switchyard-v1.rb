# EPRS — Gravity Switchyard v1
#
# Musical idea: an industrial dance machine keeps changing the size of the
# floor beneath it. Cells move through 4/4, 7/8, and 5/8 while a five-hit kick
# orbit, a crooked backbeat, and a microtonal bass rail keep colliding.
#
# Finite and deterministic: 24 cells, built-in sounds only, no live_loop,
# network, MIDI, microphone, or external samples. Record a complete pass in
# Sonic Pi, then inspect and review the WAV through EPRS.

use_bpm 142
use_random_seed 1427510
set_volume! 0.58

cell_steps = (ring 16, 14, 10, 14, 16, 10)
roots = (ring :d1, :f1, :c1, :ab0, :eb1, :b0)

with_fx :reverb, room: 0.38, mix: 0.10 do
  with_fx :distortion, distort: 0.16, mix: 0.12 do
    24.times do |cell|
      steps = cell_steps[cell]
      root = roots[cell]
      section = if cell < 4
                  :ignition
                elsif cell < 12
                  :switchyard
                elsif cell < 16
                  :zero_gravity
                elsif cell < 22
                  :redline
                else
                  :derail
                end

      cue section if [0, 4, 12, 16, 22].include?(cell)

      kick_count = section == :zero_gravity ? 2 : (section == :redline ? 7 : 5)
      kick_orbit = spread(kick_count, steps).rotate(cell * 3)
      metal_orbit = spread(7, steps).rotate(cell * 5 + 1)

      steps.times do |step|
        downbeat = step == 0
        last_step = step == steps - 1
        backbeat = step == (steps / 2)

        if kick_orbit[step] && section != :ignition
          sample :bd_tek,
            amp: (downbeat ? 0.72 : 0.48),
            cutoff: (section == :redline ? 118 : 98)
        elsif downbeat
          sample :bd_boom, amp: 0.52, cutoff: 82
        end

        if backbeat || (section == :derail && [3, steps - 3].include?(step))
          sample :sn_zome,
            amp: (backbeat ? 0.46 : 0.25),
            rate: (cell.odd? ? 0.86 : 1.14),
            pan: (cell.even? ? -0.16 : 0.16)
        end

        if metal_orbit[step] && section != :zero_gravity
          sample :elec_tick,
            amp: (step.even? ? 0.13 : 0.07),
            rate: 0.75 + (step % 5) * 0.16,
            pan: -0.65 + (step.to_f / steps) * 1.3
        end

        if last_step && [3, 7, 11, 15, 21, 23].include?(cell)
          sample :drum_tom_mid_hard,
            amp: 0.34,
            rate: (cell == 23 ? 0.52 : 1.18),
            pan: 0.28
        end

        # The fractional offsets bend the bass rail out of equal temperament.
        if downbeat || (section != :ignition && step == steps - 4)
          use_synth :fm
          play root + (step.zero? ? 0 : 6.67),
            release: (section == :zero_gravity ? 0.42 : 0.18),
            depth: 1.4,
            divisor: 1.005,
            cutoff: (section == :redline ? 92 : 70),
            amp: (section == :zero_gravity ? 0.32 : 0.44)
        end

        if section == :redline && [1, 6, 9].include?(step % 10)
          use_synth :prophet
          play chord(root + 24, :minor, num_octaves: 2),
            attack: 0.005,
            release: 0.07,
            cutoff: 105 + (step % 3) * 6,
            amp: 0.10,
            pan: (step.even? ? -0.38 : 0.38)
        end

        sleep 0.25
      end
    end
  end
end
