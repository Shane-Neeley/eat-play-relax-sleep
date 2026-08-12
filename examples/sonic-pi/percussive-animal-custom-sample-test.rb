# Portable Sonic Pi 5 custom-sample audition.
# Replace SAMPLE_PATH with a permitted local WAV, AIFF, or FLAC before running.
# Keep the iNaturalist reference and EPRS sidecar immutable and credited.
SAMPLE_PATH = "/absolute/path/to/cricket-frog-pulse-one-shot.wav"

use_bpm 120
set_volume! 0.55

4.times do |bar|
  sample SAMPLE_PATH, start: 0.0, finish: 1.0, rate: (bar.even? ? 1.0 : 0.82), amp: 0.32
  sample :bd_haus, amp: 0.28 if bar.even?
  sleep 1
  sample SAMPLE_PATH, start: 0.18, finish: 0.82, rate: 1.25, amp: 0.22
  sleep 1
  sample :sn_dub, amp: 0.16
  sleep 2
end
