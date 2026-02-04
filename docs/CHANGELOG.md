# CHANGELOG

<!-- version list -->

## v0.7.0 (2026-02-04)

### Build System

- **deps**: Bump the github-actions group with 3 updates
  ([`7528bba`](https://github.com/theseriff/jobify/commit/7528bba485a1f2a6277a07ccf0dc1d602ebd6fde))

- **deps**: Bump the pip group with 11 updates
  ([`252943f`](https://github.com/theseriff/jobify/commit/252943f52077132d7d9bd04a5acbfb8317fd6a00))

### Documentation

- Add guide for immediate execution via .push()
  ([`0499e5c`](https://github.com/theseriff/jobify/commit/0499e5c604d364290e8db793c6ad63b92b4e0474))

### Features

- **scheduler**: Introduce .push() as a concise alternative to .delay(0)
  ([`60db048`](https://github.com/theseriff/jobify/commit/60db048507254c5e67eaa13c5261746526cd7f83))


## v0.6.1 (2026-02-02)

### Bug Fixes

- **scheduler**: Getting origin_arguments instead bound.argument
  ([`1e68c2f`](https://github.com/theseriff/jobify/commit/1e68c2f14b91dcf33ac41df2bf3c7a2d2e10c726))


## v0.6.0 (2026-01-30)

### Documentation

- Add contributing guidelines and update documentation
  ([`e77b483`](https://github.com/theseriff/jobify/commit/e77b483382e68520cf974f9608951a5553423782))

- Document OuterMiddleware, OuterContext and force parameter
  ([`0d2e139`](https://github.com/theseriff/jobify/commit/0d2e139ca8343bc19023e3ad79532f671246c643))

- Update README.md
  ([`9969e02`](https://github.com/theseriff/jobify/commit/9969e02b1b0fd9325eb843925949e4c14e327087))

### Features

- **middleware**: Introduce outer middleware for job scheduling
  ([`2a9d366`](https://github.com/theseriff/jobify/commit/2a9d3660ff28eab5043969b08afc9698c96aedff))

- **router**: Support custom route_class for Jobify and JobRouter
  ([`e32f94a`](https://github.com/theseriff/jobify/commit/e32f94a6bfd72acca250dd647217a45b9109b0b2))


## v0.5.2 (2026-01-25)

### Bug Fixes

- Add name field to Runnable for better debugging
  ([`8ce04ca`](https://github.com/theseriff/jobify/commit/8ce04ca16c0521b6bfca3eb6fc6b406a384841c4))

### Documentation

- Add comprehensive real-world backup application example
  ([`f58bf11`](https://github.com/theseriff/jobify/commit/f58bf1117a564835b57f7c6d27d140b2da4834fe))

- Update examples and upgrade build dependencies
  ([`0d121c2`](https://github.com/theseriff/jobify/commit/0d121c275abaa89f2332dec7d76df0b09adb399b))

- Update link misfire_policy and update ruff configuration
  ([`b5062e5`](https://github.com/theseriff/jobify/commit/b5062e5a5a072a633f393bc22b8361002c8bd5de))


## v0.5.1 (2026-01-23)

### Bug Fixes

- **core**: Sync trigger offset in storage during schedule restoration
  ([`2c4fed8`](https://github.com/theseriff/jobify/commit/2c4fed8854da59540791af8baadff2cd809cc816))


## v0.5.0 (2026-01-22)

### Features

- **cron**: Implement stateful run_count and automatic database cleanup
  ([`35ed100`](https://github.com/theseriff/jobify/commit/35ed10003c86b84c241cf234cd1a568c736bc78d))


## v0.4.0 (2026-01-21)

### Bug Fixes

- **jobify.shutdown**: Order cancel jobs changes
  ([`f18a3cd`](https://github.com/theseriff/jobify/commit/f18a3cd9d03d6801f0a86ad847fda967f774c66f))

### Documentation

- Update cron documentation and add integrations page
  ([`9192feb`](https://github.com/theseriff/jobify/commit/9192febc00f923d71c959fde0d9caf21a9a4f1f8))

### Features

- **scheduler**: Implement idempotent start_date for cron jobs
  ([`2af4b89`](https://github.com/theseriff/jobify/commit/2af4b898ab9f78020eeb7a64cde85e16b4dfaf5f))


## v0.3.3 (2026-01-19)

### Bug Fixes

- Ensure signals are captured and restored during wait_all
  ([`0db3164`](https://github.com/theseriff/jobify/commit/0db31647183818db07302a1340951b96d87c2ea7))


## v0.3.2 (2026-01-17)

### Performance Improvements

- **wait_all**: Implement idle state tracking using asyncio.Event
  ([`6d8b3d0`](https://github.com/theseriff/jobify/commit/6d8b3d09fcfa56d166d24f4c44f86e105a1bf7a9))


## v0.3.1 (2026-01-17)

### Bug Fixes

- Resolve cron lifecycle, context injection, and misfire policy issues
  ([`23e8b4f`](https://github.com/theseriff/jobify/commit/23e8b4fcd21199697a5543b2c2a7aceffc60c083))


## v0.3.0 (2026-01-16)

### Bug Fixes

- **resolve_name**: Robust task ID generation via inspect and pathlib
  ([`1e6683d`](https://github.com/theseriff/jobify/commit/1e6683d64efe64c06b2304e3f5af1fb2fc61c56d))

### Documentation

- Clean up formatting and improve cross-referencing
  ([`965511b`](https://github.com/theseriff/jobify/commit/965511b16a514cf5fa544d84dd85ef89c5f6089f))

- Update dynamic scheduling docs with replace parameter
  ([`bc320c8`](https://github.com/theseriff/jobify/commit/bc320c8e2d39c02995359703a99dc7d611bee690))

### Features

- Allow replacing existing jobs by ID
  ([`64191b7`](https://github.com/theseriff/jobify/commit/64191b70790c2a59819649ec360f018b674b9bb1))


## v0.2.1 (2026-01-15)

### Bug Fixes

- Correct cron restoration and misfire handling on startup
  ([`39a262e`](https://github.com/theseriff/jobify/commit/39a262edf857082b545abf5e0f43e016837119e6))

- **storage/sqlite**: Prevent segmentation fault on shutdown
  ([`657f465`](https://github.com/theseriff/jobify/commit/657f46563091146cb0a0622101ed22a05d8de586))


## v0.2.0 (2026-01-13)

### Bug Fixes

- Add offset to CronArguments for proper schedule restoration
  ([`e223416`](https://github.com/theseriff/jobify/commit/e223416fdba22ffccf6ca6f9b8486276eb4f4e9a))

### Documentation

- Add misfire policy documentation and improve cron configuration
  ([`2f582a8`](https://github.com/theseriff/jobify/commit/2f582a8c34dc7887f55081929508f9a0dbae137a))

- Update feature comparison table and dynamic scheduling examples
  ([`2f582a8`](https://github.com/theseriff/jobify/commit/2f582a8c34dc7887f55081929508f9a0dbae137a))

### Features

- Add misfire policy support and improve serializers
  ([`7d93696`](https://github.com/theseriff/jobify/commit/7d936969e5af0af77c681cf041eed50c0042ab16))

- Add ZoneInfo serialization support to JSON extended encoder/decoder
  ([`3e97f81`](https://github.com/theseriff/jobify/commit/3e97f8100cc0e040bebf2a5484c8542e3564903d))

- Simplify API, add misfire policy, and improve storage
  ([`7a02a74`](https://github.com/theseriff/jobify/commit/7a02a7406096a2e57e57d940e4cef0232ab236cc))

- **scheduler**: Implement code-first reconciliation and misfire foundation
  ([`9867327`](https://github.com/theseriff/jobify/commit/98673270570818738f062522bf05377c22775d3a))


## v0.1.2 (2026-01-07)

### Bug Fixes

- **core**: Sync cron state with DB to fix restart behavior
  ([#66](https://github.com/theseriff/jobify/pull/66),
  [`07e8df3`](https://github.com/theseriff/jobify/commit/07e8df32e1e4e372f6be3c3db9da2f67c9068693))

### Build System

- **deps**: Bump the github-actions group with 5 updates
  ([#65](https://github.com/theseriff/jobify/pull/65),
  [`9a96ee2`](https://github.com/theseriff/jobify/commit/9a96ee203610f1c04b5ac0f7d31876051dd02428))

### Documentation

- Fix example lifespan ([#65](https://github.com/theseriff/jobify/pull/65),
  [`9a96ee2`](https://github.com/theseriff/jobify/commit/9a96ee203610f1c04b5ac0f7d31876051dd02428))

- Update comparison table and add note about durable performance
  ([#66](https://github.com/theseriff/jobify/pull/66),
  [`07e8df3`](https://github.com/theseriff/jobify/commit/07e8df32e1e4e372f6be3c3db9da2f67c9068693))

- Update middleware examples and improve type hints
  ([#66](https://github.com/theseriff/jobify/pull/66),
  [`07e8df3`](https://github.com/theseriff/jobify/commit/07e8df32e1e4e372f6be3c3db9da2f67c9068693))


## v0.1.1 (2025-12-31)

### Bug Fixes

- Re-release due to pypi version conflict
  ([`c75e186`](https://github.com/theseriff/jobify/commit/c75e186a76b0a48b12627d5c9ce74147540dd861))


## v0.1.0 (2025-12-31)

- Initial Release
