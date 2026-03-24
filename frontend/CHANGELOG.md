# Changelog

## [1.17.0](https://github.com/yuyash/auto-forex-web-service/compare/frontend-v1.16.0...frontend-v1.17.0) (2026-03-24)

### Features

- **strategy:** add mobile responsive layout and trend/counter filter ([#177](https://github.com/yuyash/auto-forex-web-service/issues/177)) ([67dc1c4](https://github.com/yuyash/auto-forex-web-service/commit/67dc1c4625aa185895cdbe2d9e4cbba4ef5b2021))

## [1.16.0](https://github.com/yuyash/auto-forex-web-service/compare/frontend-v1.15.4...frontend-v1.16.0) (2026-03-24)

### Features

- **strategy:** add resizable sidebar and independent scroll to strat… ([#173](https://github.com/yuyash/auto-forex-web-service/issues/173)) ([8ff523a](https://github.com/yuyash/auto-forex-web-service/commit/8ff523ae32b9e7171d5d75ec82f9a11af01e4c8f))
- **strategy:** add resizable sidebar and independent scroll to strategy tab ([8ff523a](https://github.com/yuyash/auto-forex-web-service/commit/8ff523ae32b9e7171d5d75ec82f9a11af01e4c8f))

## [1.15.4](https://github.com/yuyash/auto-forex-web-service/compare/frontend-v1.15.3...frontend-v1.15.4) (2026-03-24)

### Bug Fixes

- **strategy:** correct snowball cycle grouping and remove duplicate i… ([#171](https://github.com/yuyash/auto-forex-web-service/issues/171)) ([967e3d7](https://github.com/yuyash/auto-forex-web-service/commit/967e3d719d16cbc62db6088d6a1750ec785f2869))
- **strategy:** correct snowball cycle grouping and remove duplicate initial entries ([967e3d7](https://github.com/yuyash/auto-forex-web-service/commit/967e3d719d16cbc62db6088d6a1750ec785f2869))

## [1.15.3](https://github.com/yuyash/auto-forex-web-service/compare/frontend-v1.15.2...frontend-v1.15.3) (2026-03-24)

### Bug Fixes

- trigger deployment ([#169](https://github.com/yuyash/auto-forex-web-service/issues/169)) ([9d3cafd](https://github.com/yuyash/auto-forex-web-service/commit/9d3cafd7bbcfea767429c7313dceb9a0e33806bc))

## [1.15.2](https://github.com/yuyash/auto-forex-web-service/compare/frontend-v1.15.1...frontend-v1.15.2) (2026-03-24)

### Bug Fixes

- **ui:** strategy tab cycle list overflow and flow chart scrolling ([#166](https://github.com/yuyash/auto-forex-web-service/issues/166)) ([d36c7f6](https://github.com/yuyash/auto-forex-web-service/commit/d36c7f6d967fb93600d3787547cff4d95140f867))

## [1.15.1](https://github.com/yuyash/auto-forex-web-service/compare/frontend-v1.15.0...frontend-v1.15.1) (2026-03-24)

### Bug Fixes

- strategy events root entry id default ([#163](https://github.com/yuyash/auto-forex-web-service/issues/163)) ([523e8a6](https://github.com/yuyash/auto-forex-web-service/commit/523e8a6ab3162e2eef92be0e2002f89c232d3e48))

## [1.15.0](https://github.com/yuyash/auto-forex-web-service/compare/frontend-v1.14.6...frontend-v1.15.0) (2026-03-23)

### Features

- add backtest export button and realized/unrealized P&L metrics to results tab ([6752c14](https://github.com/yuyash/auto-forex-web-service/commit/6752c14c30940641924703a6ad4ef0dac9064aed))
- add color theme ([#26](https://github.com/yuyash/auto-forex-web-service/issues/26)) ([cff293a](https://github.com/yuyash/auto-forex-web-service/commit/cff293ad70742432db2192706b8528d751d67356))
- Add date into OHLC X-Axis ([654305d](https://github.com/yuyash/auto-forex-web-service/commit/654305d86803eeb53f852a067e0bf6206b52a9b1))
- Add pip_size and instrument fields to backtest tasks and fix UI… ([#16](https://github.com/yuyash/auto-forex-web-service/issues/16)) ([5a71b6b](https://github.com/yuyash/auto-forex-web-service/commit/5a71b6b1ef624dc4367e224af29f4ca8e93d63ae))
- add snowball strategy ([#69](https://github.com/yuyash/auto-forex-web-service/issues/69)) ([e43eaef](https://github.com/yuyash/auto-forex-web-service/commit/e43eaefacd5a339b657a9e6348d3cc7f039019c0))
- add strategy defaults API and configuration UX improvements ([c69ce85](https://github.com/yuyash/auto-forex-web-service/commit/c69ce8558337f2af7f49a459d5fb5f61970768fe))
- add task summary API and migrate detail views to unified summary ([#35](https://github.com/yuyash/auto-forex-web-service/issues/35)) ([09e7bd8](https://github.com/yuyash/auto-forex-web-service/commit/09e7bd8112a7c67ad3186f25e47035368fae5975))
- add unified task results API + migrate UI; normalize equity curve ([b17367a](https://github.com/yuyash/auto-forex-web-service/commit/b17367abbff41483799c2d37a1dfbad9eb8500bc))
- **api:** migrate task execution APIs to execution_run_id ([#44](https://github.com/yuyash/auto-forex-web-service/issues/44)) ([b0d5332](https://github.com/yuyash/auto-forex-web-service/commit/b0d5332a5069aaa1fe038151926302f0485cf6be))
- **auth:** surface whitelist-blocked login failures ([64d7392](https://github.com/yuyash/auto-forex-web-service/commit/64d7392bee2645de932e7e39dd67211ec5580db5))
- celery resilience recovery ([#42](https://github.com/yuyash/auto-forex-web-service/issues/42)) ([dfd0f3f](https://github.com/yuyash/auto-forex-web-service/commit/dfd0f3fb5bdfd271927356d3bd07307adea27d55))
- event scope queue refactor ([#48](https://github.com/yuyash/auto-forex-web-service/issues/48)) ([220238c](https://github.com/yuyash/auto-forex-web-service/commit/220238c7497cb7f0602c1ba3b7d567bd3c657d29))
- **events:** enforce 1:1 canonical floor strategy events across backend+frontend ([4af619a](https://github.com/yuyash/auto-forex-web-service/commit/4af619a14a102916aad7a0ddde6e84a0573c67aa))
- **execution:** make reruns create executions + improve logs; hide non-layer chart labels. ([e1c96e5](https://github.com/yuyash/auto-forex-web-service/commit/e1c96e55f5817d5b9272078a95be5fde75b870a2))
- **floor:** default momentum to candle lookback ([d5b5f9c](https://github.com/yuyash/auto-forex-web-service/commit/d5b5f9c17921938ff624a94ef849aaa1e01299dd))
- **frontend:** improve task detail UI for positions and price ticker ([#101](https://github.com/yuyash/auto-forex-web-service/issues/101)) ([0aef6a8](https://github.com/yuyash/auto-forex-web-service/commit/0aef6a8bf72d1af03d9c0b9f7dd45948cd75ab9f))
- hedging and trend panel ([#85](https://github.com/yuyash/auto-forex-web-service/issues/85)) ([8743b6a](https://github.com/yuyash/auto-forex-web-service/commit/8743b6ac2edf51f429039edb705dcbd8a2555154))
- improve market task logging ([#100](https://github.com/yuyash/auto-forex-web-service/issues/100)) ([3512d2d](https://github.com/yuyash/auto-forex-web-service/commit/3512d2dbcf3ac9a85561f734d29b2e03bbf5e3a8))
- refresh token security ([#51](https://github.com/yuyash/auto-forex-web-service/issues/51)) ([4eb53b4](https://github.com/yuyash/auto-forex-web-service/commit/4eb53b4bd67af15ffa5a9d3a6fc695e28612058f))
- Replace pause/resume with 2 stop options for trading tasks ([f58c428](https://github.com/yuyash/auto-forex-web-service/commit/f58c4286af6b7bbc2a1b1cd25fc2b9f05189630a))
- **settings:** consolidate profile into settings, add display/data/c… ([#79](https://github.com/yuyash/auto-forex-web-service/issues/79)) ([8035b8b](https://github.com/yuyash/auto-forex-web-service/commit/8035b8b72f48ea5af67964696b622f7be1d59e29))
- **settings:** consolidate profile into settings, add display/data/chart preferences ([8035b8b](https://github.com/yuyash/auto-forex-web-service/commit/8035b8b72f48ea5af67964696b622f7be1d59e29))
- snowball strategy tab design ([#137](https://github.com/yuyash/auto-forex-web-service/issues/137)) ([ef21bc0](https://github.com/yuyash/auto-forex-web-service/commit/ef21bc0b3f97b40f70722f4d937c57de6b67a513))
- **trading:** add planned_exit_price_formula to strategy events and … ([#96](https://github.com/yuyash/auto-forex-web-service/issues/96)) ([13c0a1b](https://github.com/yuyash/auto-forex-web-service/commit/13c0a1b3263f4b01a2d578bf7e21edda67afaebd))
- **trading:** add planned_exit_price_formula to strategy events and improve mobile UI ([13c0a1b](https://github.com/yuyash/auto-forex-web-service/commit/13c0a1b3263f4b01a2d578bf7e21edda67afaebd))
- **trading:** enforce page/page_size pagination across logs & results endpoints ([2d66aad](https://github.com/yuyash/auto-forex-web-service/commit/2d66aad0f6b9b40f133fff5e5ae42388fbeb1f90))
- **trading:** improve trading system with enhanced events, positions, and UI components ([a356dad](https://github.com/yuyash/auto-forex-web-service/commit/a356dad5618639968719328f4ae257e843568838))
- **trading:** improve trading system with enhanced events, positions… ([#91](https://github.com/yuyash/auto-forex-web-service/issues/91)) ([a356dad](https://github.com/yuyash/auto-forex-web-service/commit/a356dad5618639968719328f4ae257e843568838))
- **trading:** improve trading UI and backend execution handling ([#93](https://github.com/yuyash/auto-forex-web-service/issues/93)) ([48ebe50](https://github.com/yuyash/auto-forex-web-service/commit/48ebe50cf5015546d37629ce32fa10b1f0011e46))
- **trading:** persist live execution artifacts + metrics checkpoints ([a6b8c8d](https://github.com/yuyash/auto-forex-web-service/commit/a6b8c8d1516a42b171b4dac8a688f489274eae88))
- **trading:** refactor app structure ([#21](https://github.com/yuyash/auto-forex-web-service/issues/21)) ([6e5db34](https://github.com/yuyash/auto-forex-web-service/commit/6e5db3461377af6596b6e1e5c6b8ce4c5df1eddb))

### Bug Fixes

- add version info ([#27](https://github.com/yuyash/auto-forex-web-service/issues/27)) ([b5217d1](https://github.com/yuyash/auto-forex-web-service/commit/b5217d16a4e476825b5521db9fe1d53c2fe9093a))
- api enhancement ([#40](https://github.com/yuyash/auto-forex-web-service/issues/40)) ([ab0b564](https://github.com/yuyash/auto-forex-web-service/commit/ab0b564dd6589279ed84556ba586d64e01dfb60d))
- **backtest:** make charts and markers robust ([25013aa](https://github.com/yuyash/auto-forex-web-service/commit/25013aa50742b17feb59d019843ac4a32d2b2f8c))
- celery task race condition ([#31](https://github.com/yuyash/auto-forex-web-service/issues/31)) ([87b3354](https://github.com/yuyash/auto-forex-web-service/commit/87b33548f2cb0c52ad1aa4a2b250944ec8e707da))
- **chart:** align market gap detection and time axis labels ([#118](https://github.com/yuyash/auto-forex-web-service/issues/118)) ([ca6a1aa](https://github.com/yuyash/auto-forex-web-service/commit/ca6a1aafd38ba1263bd9802ecfc4c3d77462fc27))
- **chart:** fixed an issue where OHLC chart doesn't follow the progre… ([#120](https://github.com/yuyash/auto-forex-web-service/issues/120)) ([777df1c](https://github.com/yuyash/auto-forex-web-service/commit/777df1c423701179c8b79f96ed1b1575de8cd844))
- **chart:** fixed an issue where OHLC chart doesn't follow the progress bar properly. ([777df1c](https://github.com/yuyash/auto-forex-web-service/commit/777df1c423701179c8b79f96ed1b1575de8cd844))
- **chart:** trading migration 0019 ([#116](https://github.com/yuyash/auto-forex-web-service/issues/116)) ([a8d9a4e](https://github.com/yuyash/auto-forex-web-service/commit/a8d9a4e7d931c2106f4b643bef05a70f6e7e133c))
- component mismatches ([#25](https://github.com/yuyash/auto-forex-web-service/issues/25)) ([f1899b4](https://github.com/yuyash/auto-forex-web-service/commit/f1899b4edaba5b123d3a39d27ff201d213569e66))
- enforce frontend npm ci and override blocked react-is ([#46](https://github.com/yuyash/auto-forex-web-service/issues/46)) ([1f200b4](https://github.com/yuyash/auto-forex-web-service/commit/1f200b475d5bedc8de79256ec03b19f5a651c877))
- **frontend:** chart dark mode colors, scroll behavior, cleanup ([#59](https://github.com/yuyash/auto-forex-web-service/issues/59)) ([3f5bfce](https://github.com/yuyash/auto-forex-web-service/commit/3f5bfce95f78cb4a526cf3088fd6d7370b0f1f2d))
- **frontend:** improve task trend panel initial load ([#129](https://github.com/yuyash/auto-forex-web-service/issues/129)) ([05e5872](https://github.com/yuyash/auto-forex-web-service/commit/05e587219994bb03732e2da0a11f141001c8f45a))
- **frontend:** reduce task trend panel polling ([#127](https://github.com/yuyash/auto-forex-web-service/issues/127)) ([851a98b](https://github.com/yuyash/auto-forex-web-service/commit/851a98b6415193d4dca42fab49038ca7e8782d00))
- **frontend:** respect column order and sort order when copying table data ([8879653](https://github.com/yuyash/auto-forex-web-service/commit/887965366e6ee9d14ab2909343682bd34eb81a6f))
- **frontend:** respect column order and sort order when copying table… ([#108](https://github.com/yuyash/auto-forex-web-service/issues/108)) ([8879653](https://github.com/yuyash/auto-forex-web-service/commit/887965366e6ee9d14ab2909343682bd34eb81a6f))
- **frontend:** unify trade markers to always show LONG/SHORT direction ([#89](https://github.com/yuyash/auto-forex-web-service/issues/89)) ([2b55994](https://github.com/yuyash/auto-forex-web-service/commit/2b559941cf234f520eff026cff47048ca3950846))
- Hide progress percentage for trading task executions ([b8cbb30](https://github.com/yuyash/auto-forex-web-service/commit/b8cbb3015a1d531dd1617488a2b53a966a8a3920))
- incremental polling reduce backend load ([#24](https://github.com/yuyash/auto-forex-web-service/issues/24)) ([980f163](https://github.com/yuyash/auto-forex-web-service/commit/980f1637145586a6955bfdb434532fcd1ed1b3e7))
- **logging:** improve production logging ([#106](https://github.com/yuyash/auto-forex-web-service/issues/106)) ([06f2fdb](https://github.com/yuyash/auto-forex-web-service/commit/06f2fdb068dda50fba59a72312a3be4e11bf4940))
- **market:** dedupe TickData bulk upserts to avoid Postgres cardinality violation ([397a45c](https://github.com/yuyash/auto-forex-web-service/commit/397a45c44561af2636297d6b2b6295f35488b400))
- **metrics:** resolve overlay display and add viewport-driven fetching ([#114](https://github.com/yuyash/auto-forex-web-service/issues/114)) ([e87a285](https://github.com/yuyash/auto-forex-web-service/commit/e87a2855b4ccf087d42cf4d4f876a48c73737a24))
- reduce API rate limit pressure and lazy-load chart data ([#38](https://github.com/yuyash/auto-forex-web-service/issues/38)) ([e733834](https://github.com/yuyash/auto-forex-web-service/commit/e733834e6bf47bd144d98d9c526f5a5eceb19745))
- Refresh executions list after start/stop/rerun actions ([fb05f8b](https://github.com/yuyash/auto-forex-web-service/commit/fb05f8b0ee3a80da2a5f535e3a1285e779f92f11))
- resolve all ty type checker errors and warnings ([#13](https://github.com/yuyash/auto-forex-web-service/issues/13)) ([1883525](https://github.com/yuyash/auto-forex-web-service/commit/1883525ce1fd5008b5c46d42e57d185620a78502))
- resolve flake8, mypy, and pylint errors in floor strategy and task executor ([b2b9949](https://github.com/yuyash/auto-forex-web-service/commit/b2b9949c5408ccbc163fdf92abd249b55f0ca88d))
- slow UI performance ([#15](https://github.com/yuyash/auto-forex-web-service/issues/15)) ([d9d8b28](https://github.com/yuyash/auto-forex-web-service/commit/d9d8b287a6c11f5e277a664456300d32498d5bf3))
- snowball manual interval input ([#77](https://github.com/yuyash/auto-forex-web-service/issues/77)) ([0bc06e0](https://github.com/yuyash/auto-forex-web-service/commit/0bc06e07c4bb314385175231af2d6907d44a58f2))
- stabilize rerun/status flow and fix floor trade PnL metrics ([d7f2325](https://github.com/yuyash/auto-forex-web-service/commit/d7f23254fef3c23c2f79e48732ef255f68ca6219))
- stabilize streams, logs, and backtest/trading results UI ([f6f15a2](https://github.com/yuyash/auto-forex-web-service/commit/f6f15a241fda3c57ca995472e6de429e64b63ef5))
- Status mismatch blocks stopping trading task. ([c407056](https://github.com/yuyash/auto-forex-web-service/commit/c4070568cc1ddba0f7694cb7127f80a24ffde903))
- **strategy:** correct snowball counter lot sizing and add retracemen… ([#87](https://github.com/yuyash/auto-forex-web-service/issues/87)) ([804e7d1](https://github.com/yuyash/auto-forex-web-service/commit/804e7d15754e8a6310dd3a03201ed805b1f327f2))
- **trading:** trading task creation ([#125](https://github.com/yuyash/auto-forex-web-service/issues/125)) ([74f1dbd](https://github.com/yuyash/auto-forex-web-service/commit/74f1dbd177acef2936fd8d0a1245c93c58a84be2))
- **ui:** fix Events/Logs tab scroll and dark mode scrollbar styling ([#63](https://github.com/yuyash/auto-forex-web-service/issues/63)) ([e068395](https://github.com/yuyash/auto-forex-web-service/commit/e0683959b4098d65a3506f7c8bc9bbeb5e2cfca8))
- **ui:** invalidate list queries after mutations to ensure fresh data ([#144](https://github.com/yuyash/auto-forex-web-service/issues/144)) ([a348b2d](https://github.com/yuyash/auto-forex-web-service/commit/a348b2d8a1f2429cc8b2b5911d4ed9ab4f562038))

### Performance Improvements

- **docker:** pin frontend build stage to amd64 to avoid QEMU emulation ([#152](https://github.com/yuyash/auto-forex-web-service/issues/152)) ([3bad5e2](https://github.com/yuyash/auto-forex-web-service/commit/3bad5e224269d83dbd86ce49d45ef1b4c12365af))
- **frontend:** reduce task trend panel polling ([851a98b](https://github.com/yuyash/auto-forex-web-service/commit/851a98b6415193d4dca42fab49038ca7e8782d00))
