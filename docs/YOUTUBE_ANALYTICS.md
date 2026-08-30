# YouTube Analytics growth readback

CashForClankers growth decisions should use channel-owner Analytics, not a
public `viewCount` sum or the Google Cloud API-service metrics page. Public
starts and qualified attention are different signals.

## Read-only local report

The bounded helper prints a JSON report and never uploads, edits metadata, or
starts OAuth:

```bash
uv run scripts/youtube_analytics_report.py \
  --start-date 2026-08-01 --end-date 2026-08-28
```

It requires the existing YouTube token to contain
`https://www.googleapis.com/auth/yt-analytics.readonly`. If it does not, the
helper stops and asks for the approved one-time YouTube auth flow; it never
silently broadens access or fabricates unavailable fields. Keep the token
outside the repository.

The report preserves a channel summary (`views`, `engagedViews`, estimated
minutes watched, and subscribers gained) plus up to 50 per-video rows with
average duration and percentage viewed. Record the date window and exact
output in a private growth note before drawing a conclusion.

## Decision rule

- For Shorts, pair views with engaged views, stayed-to-watch/swiped-away,
  average percentage viewed, and subscribers per 1,000 engaged views.
- For long-form, pair impressions and CTR with first-30-second retention,
  average percentage viewed, watch minutes per impression, returning viewers,
  and subscribers per 1,000 views.
- Compare matched formats over a fixed seven-day window. A title or thumbnail
  is a win only when qualified attention improves with the click signal; raw
  views alone are not a win.
- While regular viewers are scarce, make one clear experiment at a time: a
  concrete title/thumbnail promise, a first-two-second musical payoff, or a
  distinct guitar-playable/process-series format. Do not respond to weak
  conversion with near-duplicate upload bursts.

## Current Studio snapshot (2026-08-29)

The authenticated Studio view for Aug 1–28 shows 1,067 channel views (+42%),
5.3 watch hours (+37%), and +2 subscribers (33% below the prior period).
Shorts contributed 735 views but only 267 engaged views, with 33.5% staying to
watch and 66.5% swiping away. Long-form showed 4.8K impressions, 3.0% CTR,
and 0:37 average view duration. Monthly audience was 335: 97.9% new viewers,
2.1% casual, and under 0.1% regular. Treat these as a discovery-without-habit
signal: strengthen the first seconds and build a repeatable series before
increasing volume.
