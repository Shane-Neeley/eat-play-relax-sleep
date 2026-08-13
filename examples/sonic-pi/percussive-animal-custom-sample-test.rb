# EPRS — Animal Drum Circle v1
#
# Musical idea: five animals occupy different percussion roles instead of one
# sample pretending to be an entire kit. Bullfrog is the low drum, woodpecker
# is wood/roll, cricket frog is wet rim, katydid is ratchet, and cicada is the
# bright carrier that opens the roof in the final section.
#
# Prepare the five attributed files with ANIMAL_PERCUSSION.md, then set one
# portable pack directory. The files are derivatives; immutable iNaturalist
# sources and provenance sidecars remain in the song's references directory.
# This is an authored composition, not a translation of animal meaning.

PACK_DIR = "/absolute/path/to/song/audio/animal-percussion-pack"
BULLFROG = "#{PACK_DIR}/bullfrog-low.wav"
WOODPECKER = "#{PACK_DIR}/woodpecker-roll.wav"
CRICKET_FROG = "#{PACK_DIR}/cricket-frog-rim.wav"
KATYDID = "#{PACK_DIR}/katydid-ratchet.wav"
CICADA = "#{PACK_DIR}/cicada-carrier.wav"

animal_sources = [BULLFROG, WOODPECKER, CRICKET_FROG, KATYDID, CICADA]
raise "Set PACK_DIR before running" if PACK_DIR.include?("/absolute/path/")
load_samples animal_sources

use_bpm 112
use_random_seed 1120505
set_volume! 0.50

bullfrog_onsets = (ring 0, 2, 4, 7, 10, 13, 15, 17)
wood_onsets = (ring 21, 22, 23, 24, 25, 27, 28, 29, 31, 34)
frog_onsets = (ring 7, 12, 19, 27, 36, 45, 63, 75, 91, 106)

with_fx :reverb, room: 0.48, mix: 0.13 do
  32.times do |bar|
    section = if bar < 4
                :field_intro
              elsif bar < 12
                :wood_and_water
              elsif bar < 20
                :night_swarm
              elsif bar < 24
                :moonbreak
              else
                :full_migration
              end

    cue section if [0, 4, 12, 20, 24].include?(bar)

    # Sustained insects become rhythmic air, not fake one-shots.
    if [:night_swarm, :full_migration].include?(section)
      in_thread do
        with_fx :slicer,
          phase: (section == :full_migration ? 0.0625 : 0.125),
          wave: 1,
          pulse_width: 0.30 + (bar % 3) * 0.08,
          mix: 1 do
          sample KATYDID,
            start: 0.05,
            finish: 0.95,
            beat_stretch: 4,
            hpf: 86,
            lpf: 119,
            amp: 0.13,
            pan: -0.28
        end
      end
    end

    if section == :full_migration && bar.even?
      in_thread do
        with_fx :slicer, phase: 0.25, wave: 2, pulse_width: 0.62, mix: 0.78 do
          sample CICADA,
            start: 0.17,
            finish: 0.28,
            beat_stretch: 4,
            hpf: 76,
            amp: 0.10,
            pan: 0.34
        end
      end
    end

    16.times do |step|
      # Low calls leave air around themselves; they are punctuation, not a
      # four-on-the-floor replacement.
      bullfrog_pattern = case section
                         when :field_intro then [0]
                         when :wood_and_water then [0, 10]
                         when :night_swarm then [0, 7, 13]
                         when :moonbreak then (bar.even? ? [0] : [14])
                         else [0, 6, 10, 14]
                         end
      if bullfrog_pattern.include?(step)
        sample BULLFROG,
          onset: bullfrog_onsets[bar + step],
          sustain: 0,
          release: 0.28,
          rate: (step.zero? ? 0.58 : 0.72),
          lpf: 72,
          amp: (step.zero? ? 0.34 : 0.23),
          pan: -0.08
      end

      wood_pattern = case section
                     when :field_intro then [8]
                     when :wood_and_water then [4, 12]
                     when :night_swarm then [4, 11, 12]
                     when :moonbreak then [12]
                     else [3, 4, 11, 12, 15]
                     end
      if wood_pattern.include?(step)
        sample WOODPECKER,
          onset: wood_onsets[bar + step],
          sustain: 0,
          release: (step == 15 ? 0.16 : 0.085),
          rate: 0.88 + (bar % 4) * 0.08,
          hpf: 54,
          amp: (step == 12 ? 0.29 : 0.20),
          pan: 0.12
      end

      frog_pattern = spread(
        section == :field_intro ? 2 : (section == :full_migration ? 9 : 5),
        16
      ).rotate(bar * 3)
      if frog_pattern[step] && section != :moonbreak
        sample CRICKET_FROG,
          onset: frog_onsets[bar * 2 + step],
          sustain: 0,
          release: 0.055,
          rate: (step.even? ? 1.06 : 1.31),
          hpf: 82,
          amp: (step % 4 == 0 ? 0.16 : 0.10),
          pan: -0.58 + step / 14.0
      end

      # Section-ending rolls use measured dense onset regions rather than a
      # synthetic tom fill.
      if [3, 11, 19, 23, 31].include?(bar) && step >= 12
        sample WOODPECKER,
          onset: wood_onsets[step + bar],
          sustain: 0,
          release: 0.065,
          rate: 0.92 + (step - 12) * 0.11,
          amp: 0.17 + (step - 12) * 0.025,
          pan: -0.45 + (step - 12) * 0.3
      end

      # A quiet synthetic fundamental appears only in the last eight bars to
      # support small-speaker translation; the animal sources remain the kit.
      if section == :full_migration && step.zero?
        use_synth :subpulse
        play :d1,
          release: 0.12,
          cutoff: 62,
          amp: 0.13
      end

      sleep 0.25
    end
  end
end
