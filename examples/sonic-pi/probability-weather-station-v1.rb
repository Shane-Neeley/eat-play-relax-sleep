# EPRS — Probability Weather Station v1
#
# Musical idea: randomness should behave like weather, not television static.
# Seeded Perlin motion slowly changes density, brightness, register, and pan;
# fixed downbeats and section boundaries keep the forecast musically legible.

use_bpm 104
use_random_seed 1049001
use_random_source :perlin
set_volume! 0.53

notes = (scale :c2, :phrygian_dominant, num_octaves: 3)

with_fx :reverb, room: 0.68, mix: 0.18 do
  24.times do |bar|
    section = if bar < 6
                :fog
              elsif bar < 14
                :pressure_front
              elsif bar < 18
                :eye
              else
                :electrical_rain
              end

    cue section if [0, 6, 14, 18].include?(bar)

    16.times do |step|
      climate = rand
      brightness = 55 + climate * 65
      density = section == :electrical_rain ? 0.72 : (section == :eye ? 0.18 : 0.43)

      sample :bd_zome,
        amp: 0.43,
        cutoff: 78 if step.zero? || (section == :pressure_front && step == 11)

      if step == 8 && section != :fog
        sample :sn_dolf, amp: 0.31, rate: 0.8 + climate * 0.55
      end

      if climate < density && section != :eye
        sample :hat_psych,
          amp: 0.045 + climate * 0.09,
          rate: 0.7 + climate * 1.8,
          pan: climate * 1.4 - 0.7,
          finish: 0.025 + climate * 0.04
      end

      if (spread(section == :electrical_rain ? 9 : 5, 16).rotate(bar))[step]
        use_synth :tech_saws
        note = notes[(climate * notes.length).floor]
        play note,
          release: 0.055 + climate * 0.16,
          cutoff: brightness,
          amp: (section == :eye ? 0.07 : 0.12),
          pan: climate * 1.2 - 0.6
      end

      if section == :eye && [0, 7, 13].include?(step)
        use_synth :hollow
        play chord(:c3 + bar % 3, :maj13).choose,
          attack: 0.08,
          release: 0.7,
          cutoff: 72,
          amp: 0.11
      end

      sleep 0.25
    end
  end
end
