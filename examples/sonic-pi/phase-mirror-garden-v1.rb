# EPRS — Phase Mirror Garden v1
#
# Musical idea: two related note streams begin as a reflection, then the right
# side walks slightly slower until the pair becomes a new harmony. Sonic Pi 5's
# ring inversion and sine phase offset make the process audible and spatial.

use_bpm 118
use_random_seed 1180257
set_volume! 0.52

source_notes = (scale :d3, :lydian_dominant, num_octaves: 2).take(9)
mirror_notes = source_notes.invert_around(:d4).reverse

with_fx :reverb, room: 0.74, mix: 0.22 do
  in_thread(name: :left_garden) do
    240.times do |step|
      if (spread 7, 15).rotate(2)[step]
        use_synth :sine
        play source_notes[step],
          phase_offset: 0,
          release: 0.14,
          amp: (step % 15 == 0 ? 0.22 : 0.12),
          pan: -0.54
      end
      sleep 0.25
    end
  end

  in_thread(name: :right_garden) do
    234.times do |step|
      if (spread 7, 15).rotate(7)[step]
        use_synth :sine
        play mirror_notes[step],
          phase_offset: 0.25,
          release: 0.14,
          amp: (step % 15 == 0 ? 0.22 : 0.12),
          pan: 0.54
      end
      sleep 0.257
    end
  end

  240.times do |step|
    sample :bd_boom, amp: 0.34, cutoff: 74 if step % 16 == 0
    sample :elec_tick, amp: 0.08, pan: 0 if step % 15 == 0

    if step % 60 == 59
      use_synth :prophet
      play chord(:d2 + (step / 60) * 2, :minor_major7),
        attack: 0.02,
        release: 1.4,
        cutoff: 76 + step / 6,
        amp: 0.16
    end
    sleep 0.25
  end
end

# Let the slower mirror and its reverb tail complete cleanly.
sleep 2
