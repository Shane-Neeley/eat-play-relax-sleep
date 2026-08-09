import test from "node:test";
import assert from "node:assert/strict";
import {cycle, kidVoiceNames, kidsPresets, mutatePattern, stepTime, toBeatScript, velocity, voices} from "../studio/beat-core.mjs";

test("symbol semantics are stable", () => {
  assert.equal(cycle("."), "x"); assert.equal(cycle("g"), ".");
  assert.ok(velocity("X") > velocity("x")); assert.ok(velocity("x") > velocity("g"));
});

test("swing delays odd sixteenths only", () => {
  assert.equal(stepTime(0, 120, 0.6), 0);
  assert.ok(stepTime(1, 120, 0.6) > 0.125);
  assert.equal(stepTime(2, 120, 0.6), 0.25);
});

test("BeatScript export is parseable-shaped", () => {
  const text = toBeatScript({title:"Test",tempo:90,swing:0.5,seed:1,patterns:{kick:"x...............",snare:"....x...........",hat:"x.x.x.x.x.x.x.x.",perc:"................"}});
  assert.match(text, /tempo 90/); assert.match(text, /track kick/); assert.match(text, /swing 0.50/);
});

test("mutation can be deterministic when random source is deterministic", () => {
  assert.equal(mutatePattern("x.x.", () => 0, 0.5), "xg.g");
});

test("kids presets remain valid one-bar patterns", () => {
  for (const preset of Object.values(kidsPresets)) {
    for (const voice of voices) assert.match(preset.patterns[voice], /^[.xXgo]{16}$/);
    assert.match(toBeatScript({...preset, seed: 7}), /bars 8/);
  }
  assert.equal(kidVoiceNames.snare, "Ghost boo");
});
