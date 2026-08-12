# EPRS — Pull Me In v1
#
# Musical question: can a beat create a reason to stay before the full groove
# arrives? This is a finite 32-bar Sonic Pi v5 arrangement, not a one-bar loop.
# The same three-note identity returns in different registers and rhythms while
# drums, bass, harmony, and density change around it.
#
# Form at 112 BPM:
#   0-3  tease      signature motif, no full backbeat
#   4-11 pocket     broken kick + answer snare
#   12-15 lift      rising bass and fills
#   16-19 drop      space, bass pickup, suspended expectation
#   20-27 hook      full payoff and octave answer
#   28-31 final     denser variation, last-bar turnaround
#
# Built-in sounds only. No network, no live loop, no external control.

use_bpm 112
use_random_seed 20260812
set_volume! 0.68

roots = (ring :c2, :ab1, :eb2, :bb1)
chord_roots = (ring :c3, :ab2, :eb3, :bb2)
chord_types = (ring :minor, :major, :major, :major)

in_thread(name: :pull_me_in_drums) do
  32.times do |bar|
    section = if bar < 4
                :tease
              elsif bar < 12
                :pocket
              elsif bar < 16
                :lift
              elsif bar < 20
                :drop
              elsif bar < 28
                :hook
              else
                :final
              end

    kick = case section
           when :tease then [0, 10]
           when :pocket then [0, 3, 6, 8, 11, 14]
           when :lift then [0, 3, 6, 8, 10, 13, 14]
           when :drop then [0, 14]
           when :hook then [0, 3, 6, 8, 10, 13, 14]
           else [0, 2, 3, 6, 8, 10, 13, 14, 15]
           end
    snare = case section
            when :tease then (bar == 3 ? [12, 15] : [])
            when :drop then (bar.odd? ? [12] : [4, 12])
            else [4, 12]
            end

    16.times do |step|
      if kick.include?(step)
        sample :bd_haus,
          amp: (step == 0 ? 0.78 : 0.58),
          cutoff: (section == :drop ? 82 : 108)
      end

      sample :sn_dub, amp: 0.56 if snare.include?(step)
      sample :perc_snap, amp: 0.18 if section != :tease && [7, 15].include?(step)

      if section == :pocket || section == :hook
        sample :drum_cymbal_closed, amp: (step.even? ? 0.24 : 0.10), finish: 0.055
        sample :drum_cymbal_closed, amp: 0.16, finish: 0.04 if [3, 11].include?(step)
      elsif section == :lift || section == :final
        sample :drum_cymbal_closed, amp: (step.even? ? 0.30 : 0.14), finish: 0.06
        sample :drum_cymbal_open, amp: 0.24, finish: 0.12 if [7, 15].include?(step)
      end

      if [3, 7, 11, 15].include?(step) && [11, 15, 19, 27, 31].include?(bar)
        sample :drum_tom_mid_soft, amp: 0.38, rate: (step == 15 ? 1.15 : 0.95)
      end

      sleep 0.25
    end
  end
end

in_thread(name: :pull_me_in_bass) do
  use_synth :subpulse
  bass_patterns = {
    tease: [0, nil, nil, nil, nil, nil, 7, nil],
    pocket: [0, nil, 0, 7, nil, 0, nil, 12],
    lift: [0, 0, 7, 12, 0, 7, 12, 14],
    drop: [0, nil, nil, nil, nil, nil, 7, 12],
    hook: [0, nil, 0, 7, nil, 0, 12, 7],
    final: [0, 7, 12, 7, 0, 7, 14, 12]
  }

  32.times do |bar|
    section = if bar < 4
                :tease
              elsif bar < 12
                :pocket
              elsif bar < 16
                :lift
              elsif bar < 20
                :drop
              elsif bar < 28
                :hook
              else
                :final
              end
    root = roots[bar % 4]
    pattern = bass_patterns[section]

    pattern.each do |offset|
      if offset
        play root + offset,
          release: (section == :drop ? 0.34 : 0.20),
          cutoff: (section == :tease ? 62 : (section == :drop ? 74 : 92)),
          amp: (section == :final ? 0.62 : 0.52)
      end
      sleep 0.5
    end
  end
end

in_thread(name: :pull_me_in_harmony) do
  use_synth :prophet
  with_fx :reverb, room: 0.62, mix: 0.18 do
    32.times do |bar|
      section = if bar < 4
                  :tease
                elsif bar < 12
                  :pocket
                elsif bar < 16
                  :lift
                elsif bar < 20
                  :drop
                elsif bar < 28
                  :hook
                else
                  :final
                end
      root = chord_roots[bar % 4]
      type = chord_types[bar % 4]

      if section == :tease
        play chord(root, type), sustain: 0.08, release: 0.42, cutoff: 74, amp: 0.15 if bar.even?
        sleep 4
      elsif section == :drop
        play chord(root, type), sustain: 0.12, release: 0.62, cutoff: 68, amp: 0.18 if bar == 16 || bar == 18
        sleep 4
      else
        play chord(root, type), sustain: 0.08, release: 0.32, cutoff: (section == :final ? 102 : 88), amp: (section == :final ? 0.25 : 0.20)
        sleep 2
        play chord(root, type), sustain: 0.04, release: 0.22, cutoff: 94, amp: 0.13 if section == :lift || section == :hook || section == :final
        sleep 2
      end
    end
  end
end

in_thread(name: :pull_me_in_motif) do
  use_synth :blade
  tease = (ring :g4, nil, :f4, :d4, nil, :c4, :d4, nil)
  pocket = (ring :g4, :g4, nil, :f4, :d4, nil, :f4, :g4)
  lift = (ring :g4, :a4, :bb4, :a4, :g4, :f4, :d4, :f4)
  hook = (ring :g4, :g4, :bb4, :a4, :g4, :f4, :d4, :f4)
  final = (ring :g4, :bb4, :c5, :bb4, :a4, :g4, :f4, :d4)

  with_fx :echo, phase: 0.375, decay: 2.5, mix: 0.12 do
    32.times do |bar|
      section = if bar < 4
                  :tease
                elsif bar < 12
                  :pocket
                elsif bar < 16
                  :lift
                elsif bar < 20
                  :drop
                elsif bar < 28
                  :hook
                else
                  :final
                end
      pattern = case section
                when :tease then tease
                when :pocket then pocket
                when :lift then lift
                when :drop then (ring nil, nil, :d4, nil, nil, nil, :f4, :g4)
                when :hook then hook
                else final
                end

      8.times do |step|
        note = pattern[step]
        if note
          play note,
            release: (section == :tease ? 0.18 : 0.13),
            cutoff: (section == :final ? 112 : (section == :hook ? 104 : 88)),
            amp: (section == :final ? 0.30 : (section == :hook ? 0.24 : 0.17))
        end
        sleep 0.5
      end
    end
  end
end

# Final two bars are intentionally audible as a turnaround, not an abrupt end.
sleep 69
