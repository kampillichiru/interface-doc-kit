# test-data: files for the data check

Used only when `Data check` is `yes` in `module.md`. The run tells you when it needs them.

For each output, a folder named by its id from `discovery.md`:

```
test-data/O01/expected.dat   result of the check SQL the run wrote, one line per row, no header
test-data/O01/actual.dat     the real output file of the legacy system for the same run date
```

Any file extension works. Use the test environment, never production.
