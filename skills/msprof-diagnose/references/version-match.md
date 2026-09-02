# Dump time vs later code

Diagnose from the **dump and the code that could have produced it**. A fix commit that landed after the dump is confirmation only. On the dump’s day that commit does not exist; `git log` will not find it.

## Primary path (required)

1. ERROR / asked gap → artifact (dic, slice, db) → reporter / channel / parser in source.
2. For host typeInfo: `unaging.additional.type_info_dic` is `level_id:str`. Level present but id missing → registration table vs `Report*`/`CallApiBegin` in **that** tree. Dic missing the id while api_event has it is enough to call **上报组件**.
3. Say what to change next (add the mapping, check RegTypeInfo ret, …) without naming a future PR.

## Later clone (optional)

If the local tree is **newer** than the dump and you happen to find a later fix, you may say it matches. Do not wait for that search, and do not treat “no later PR in git” as unknown.

If the clone is newer than the dump, state that. Prefer a tag/commit at or before dump time when the user can provide it.
