This directory contains CODE ONLY, copied byte for byte from
`experiment/api-market-2-playable-odds` at
`12ebe32220d04b7488889b2c7c4384ff47eb9d2e`.

`source_manifest.json` records SHA256 and original Git blob IDs. The regression
test verifies both for every source/config file. This makes CI independent of
an unavailable historical branch checkout without replacing its algorithms.

No API responses, predictions, prices, results or historical archives are
stored here. Explicit unit inputs are generated in temporary directories by
`test_multimodel_v2_rollout.py`; socket connections are forbidden there.
The producer fixture and its configuration must remain byte-identical.
