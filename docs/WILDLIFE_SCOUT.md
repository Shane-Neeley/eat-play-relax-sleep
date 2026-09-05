# Regional creative discovery

Run a bounded recent-page scout before the daily producer selects its animal seed:

```sh
uv run python scripts/wildlife_scout.py --place-id 10 --days 7 \
  --out .eprs-local/producer/oregon-DATE.json
uv run python scripts/wildlife_scout.py --place-id 10 --days 30 --sounds \
  --out .eprs-local/producer/oregon-sounds-DATE.json
```

Place 10 is Oregon. Resolve other regions through iNaturalist places first. Space requests by at least 1.1 seconds. Use unique output names. Failed requests do not replace prior reports. No notifications are sent by this command.

`--watch-taxon` and `--seen-taxon` accept repeated taxon IDs; `--limit` controls the shortlist. Use recently selected taxa as seen, not every downloaded candidate: overflow must remain eligible. The ranking considers watchlists, community status flags, a global record-count proxy, identification quality and usable media. It excludes plants/captive observations and omits conservation/rarity bonuses for introduced taxa. It ranks only the latest 100 results, not the entire region; use narrower regional or sound queries when appropriate. Global counts do not establish biological rarity. The report exposes no precise locations.

Audio and images retain separate licenses and credits. CC0 and attributed CC BY are candidates for reuse, not proof of species identity or completed release clearance. Other media remain reference-only. The endpoint does not supply video assets. Field photos can inform separately credited video compositions; illustrations must be labelled as such.

Open `studio/lab.html` via `make studio`, import a report, select seeds and export a production brief. The brief is a producer input, not an execution or publication action. Read its intent, voice, tuning, album, picture and detailed instructions alongside `docs/PRODUCER.md`.

For actual sound use, freeze the source with `eprs inaturalist`, run study and audit, select a verified audible window, and preserve the original plus cut lineage. Keep classifications separate from detection timestamps. Use pulse-train, sustained-call or transient behavior based on the recording. Do not invent listening evidence.
