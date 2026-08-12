# EPRS Sonic Pi v5 starter: a bounded, deterministic 12-bar groove.
#
# Musical intent: a soft but usable pocket for a vocal, guitar, or found sound.
# Technical intent: keep the source portable, the layers conservative, and the
# recording bounded. Record the resulting WAV in Sonic Pi, then inspect/review
# it through EPRS. This is not an approved master or release picture.

use_bpm 96
set_volume! 0.55

bass_notes = (ring :c2, :c2, :g1, :a1)
lead_notes = (ring :c4, :d4, :g4, :f4)

with_fx :reverb, room: 0.45, mix: 0.12 do
  12.times do |bar|
    4.times do |beat|
      sample :bd_haus, amp: 0.28 if [0, 2].include?(beat)
      sample :sn_dub, amp: 0.16 if [1, 3].include?(beat)

      synth :prophet,
        note: bass_notes[bar % 4],
        sustain: 0.08,
        release: 0.22,
        cutoff: 72,
        amp: 0.18

      if beat == 1
        synth :blade,
          note: lead_notes[bar % 4],
          sustain: 0.05,
          release: 0.16,
          cutoff: 90,
          amp: 0.12
      end

      sleep 1
    end
  end
end
