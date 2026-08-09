# EPRS semantic visual cues for a local visual instrument.
# Continuous audio reactivity should come from the rendered/live audio signal.
# Use these OSC events only for musical meaning that an FFT cannot know.
# The receiver port is deliberately localhost-only in the default workflow.

use_osc "127.0.0.1", 57121

define :visual_cue do |event, intensity = 1.0, value = 0.0|
  osc "/eprs/visual", event.to_s, intensity, value
end

# Copy these calls into the actual composition at authored musical moments:
# visual_cue :door_open, 0.8
# visual_cue :live_instrument_enter, 1.0, 4       # value can identify a take/voice
# visual_cue :drop_machine, 1.0
# visual_cue :room_only, 0.55

# Optional quarter-note clock for a live renderer that needs shared pulse.
# Keep it disabled when the image should follow free time or recorded performance.
# live_loop :visual_clock do
#   visual_cue :quarter, 0.25, tick
#   sleep 1
# end
