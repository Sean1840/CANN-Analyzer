# Log focus

Collect every level into the evidence pack. **Analysis and the user-facing problem list are not the inventory.**

## What to treat as a problem

1. **ERROR** (and slog/plog EVENT that names a failure or error code).
2. **What the user asked** — e.g. “why is xxx missing / empty / unnamed”. Then pull the WARNING/INFO that sit on that same data path (same typeInfo, same file, same channel, same parser).
3. WARNING/INFO **only if they explain an ERROR or the asked gap**.

## What not to do

- Do not walk the full WARNING list and turn each empty optional table / missing db / `No Events` / `already exists` into its own fault.
- Many profiler WARNINGs are the parser probing capabilities that were off, unsupported on this chip, or unused in this scene. Those are normal.
- If there is no ERROR and the user did not name a missing artifact, stop after the ERROR (or say there is no ERROR). Do not invent a 20-item issue catalog from `mindstudio_profiler_log`.

## Grouping

When several logs share one cause, report **one** problem. Do not list every downstream “table not found” as a separate ticket.
