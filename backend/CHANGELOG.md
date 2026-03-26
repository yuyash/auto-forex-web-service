# Changelog

## [1.17.0](https://github.com/yuyash/auto-forex-web-service/compare/backend-v1.16.5...backend-v1.17.0) (2026-03-26)


### Features

* **trading:** add sequence_number to preserve event ordering within … ([#206](https://github.com/yuyash/auto-forex-web-service/issues/206)) ([31f686e](https://github.com/yuyash/auto-forex-web-service/commit/31f686ead46296962ef7fa849ed9ff90afee4746))
* **trading:** add sequence_number to preserve event ordering within same tick ([31f686e](https://github.com/yuyash/auto-forex-web-service/commit/31f686ead46296962ef7fa849ed9ff90afee4746))

## [1.16.5](https://github.com/yuyash/auto-forex-web-service/compare/backend-v1.16.4...backend-v1.16.5) (2026-03-26)


### Bug Fixes

* **strategy:** DB fallback for cycle_id, granularity selector, chart … ([#204](https://github.com/yuyash/auto-forex-web-service/issues/204)) ([794a7cc](https://github.com/yuyash/auto-forex-web-service/commit/794a7cc1911528b910fc953b0c126d7023db6567))
* **strategy:** DB fallback for cycle_id, granularity selector, chart fixes ([794a7cc](https://github.com/yuyash/auto-forex-web-service/commit/794a7cc1911528b910fc953b0c126d7023db6567))

## [1.16.4](https://github.com/yuyash/auto-forex-web-service/compare/backend-v1.16.3...backend-v1.16.4) (2026-03-26)


### Bug Fixes

* chart marker positions ([#197](https://github.com/yuyash/auto-forex-web-service/issues/197)) ([a9794a3](https://github.com/yuyash/auto-forex-web-service/commit/a9794a331f766c403e76d6e294c262943f8f4d66))

## [1.16.3](https://github.com/yuyash/auto-forex-web-service/compare/backend-v1.16.2...backend-v1.16.3) (2026-03-25)


### Bug Fixes

* cycle id assignment and chart ([#190](https://github.com/yuyash/auto-forex-web-service/issues/190)) ([d3f7700](https://github.com/yuyash/auto-forex-web-service/commit/d3f77005565781c4b3629d3f12bfc3d9b542b9d4))

## [1.16.2](https://github.com/yuyash/auto-forex-web-service/compare/backend-v1.16.1...backend-v1.16.2) (2026-03-25)


### Bug Fixes

* cycle based snowball strategy ([#188](https://github.com/yuyash/auto-forex-web-service/issues/188)) ([4cbd2be](https://github.com/yuyash/auto-forex-web-service/commit/4cbd2be327178526c0828d871bc77c43e31a05de))

## [1.16.1](https://github.com/yuyash/auto-forex-web-service/compare/backend-v1.16.0...backend-v1.16.1) (2026-03-25)


### Bug Fixes

* **strategy:** trigger deployment for cycle-based snowball refactor ([#182](https://github.com/yuyash/auto-forex-web-service/issues/182)) ([13f6bc4](https://github.com/yuyash/auto-forex-web-service/commit/13f6bc43549cb8b1d359516a8c9590df142c9306))

## [1.16.0](https://github.com/yuyash/auto-forex-web-service/compare/backend-v1.15.4...backend-v1.16.0) (2026-03-24)


### Features

* **strategy:** add display cycle splitting and OHLC chart visualization ([#179](https://github.com/yuyash/auto-forex-web-service/issues/179)) ([20f97ab](https://github.com/yuyash/auto-forex-web-service/commit/20f97ab49f1f48126bf51cd35118b511b98e7192))

## [1.15.4](https://github.com/yuyash/auto-forex-web-service/compare/backend-v1.15.3...backend-v1.15.4) (2026-03-24)


### Bug Fixes

* strategy grouping parent chain ([#175](https://github.com/yuyash/auto-forex-web-service/issues/175)) ([19461d6](https://github.com/yuyash/auto-forex-web-service/commit/19461d62e3d0329d3d3360142eb206b8ee9ff944))

## [1.15.3](https://github.com/yuyash/auto-forex-web-service/compare/backend-v1.15.2...backend-v1.15.3) (2026-03-24)


### Bug Fixes

* trigger deployment ([#169](https://github.com/yuyash/auto-forex-web-service/issues/169)) ([9d3cafd](https://github.com/yuyash/auto-forex-web-service/commit/9d3cafd7bbcfea767429c7313dceb9a0e33806bc))

## [1.15.2](https://github.com/yuyash/auto-forex-web-service/compare/backend-v1.15.1...backend-v1.15.2) (2026-03-24)


### Bug Fixes

* strategy events root entry id default ([#163](https://github.com/yuyash/auto-forex-web-service/issues/163)) ([523e8a6](https://github.com/yuyash/auto-forex-web-service/commit/523e8a6ab3162e2eef92be0e2002f89c232d3e48))

## [1.15.1](https://github.com/yuyash/auto-forex-web-service/compare/backend-v1.15.0...backend-v1.15.1) (2026-03-24)


### Bug Fixes

* resolve backend code quality issues ([#160](https://github.com/yuyash/auto-forex-web-service/issues/160)) ([def2e22](https://github.com/yuyash/auto-forex-web-service/commit/def2e22766e4192779932619406516f10ffc42b6))

## [1.15.0](https://github.com/yuyash/auto-forex-web-service/compare/backend-v1.14.6...backend-v1.15.0) (2026-03-23)


### Features

* Add --role-arn option to load-data command. ([a1c3a47](https://github.com/yuyash/auto-forex-web-service/commit/a1c3a47c963cf6780ea675a5baad04023c1e0e0f))
* add backtest export button and realized/unrealized P&L metrics to results tab ([6752c14](https://github.com/yuyash/auto-forex-web-service/commit/6752c14c30940641924703a6ad4ef0dac9064aed))
* add management commands for backtest, trading, and config CRUD … ([#54](https://github.com/yuyash/auto-forex-web-service/issues/54)) ([fc4c4ee](https://github.com/yuyash/auto-forex-web-service/commit/fc4c4ee6d3ddf86daefc73eda090fb95ef2e6ae5))
* add management commands for backtest, trading, and config CRUD operations ([fc4c4ee](https://github.com/yuyash/auto-forex-web-service/commit/fc4c4ee6d3ddf86daefc73eda090fb95ef2e6ae5))
* Add pip_size and instrument fields to backtest tasks and fix UI… ([#16](https://github.com/yuyash/auto-forex-web-service/issues/16)) ([5a71b6b](https://github.com/yuyash/auto-forex-web-service/commit/5a71b6b1ef624dc4367e224af29f4ca8e93d63ae))
* add snowball strategy ([#69](https://github.com/yuyash/auto-forex-web-service/issues/69)) ([e43eaef](https://github.com/yuyash/auto-forex-web-service/commit/e43eaefacd5a339b657a9e6348d3cc7f039019c0))
* add strategy defaults API and configuration UX improvements ([c69ce85](https://github.com/yuyash/auto-forex-web-service/commit/c69ce8558337f2af7f49a459d5fb5f61970768fe))
* add task summary API and migrate detail views to unified summary ([#35](https://github.com/yuyash/auto-forex-web-service/issues/35)) ([09e7bd8](https://github.com/yuyash/auto-forex-web-service/commit/09e7bd8112a7c67ad3186f25e47035368fae5975))
* add unified task results API + migrate UI; normalize equity curve ([b17367a](https://github.com/yuyash/auto-forex-web-service/commit/b17367abbff41483799c2d37a1dfbad9eb8500bc))
* **api:** migrate task execution APIs to execution_run_id ([#44](https://github.com/yuyash/auto-forex-web-service/issues/44)) ([b0d5332](https://github.com/yuyash/auto-forex-web-service/commit/b0d5332a5069aaa1fe038151926302f0485cf6be))
* **auth:** surface whitelist-blocked login failures ([64d7392](https://github.com/yuyash/auto-forex-web-service/commit/64d7392bee2645de932e7e39dd67211ec5580db5))
* auto-resume trading tasks on worker startup ([c1a1ce0](https://github.com/yuyash/auto-forex-web-service/commit/c1a1ce0dda811ebd3c9f22dec06aedb114f12258))
* celery resilience recovery ([#42](https://github.com/yuyash/auto-forex-web-service/issues/42)) ([dfd0f3f](https://github.com/yuyash/auto-forex-web-service/commit/dfd0f3fb5bdfd271927356d3bd07307adea27d55))
* **celery:** db backup s3 ([#154](https://github.com/yuyash/auto-forex-web-service/issues/154)) ([241bae4](https://github.com/yuyash/auto-forex-web-service/commit/241bae421ef664159a99245f963eeae879b9a400))
* event scope queue refactor ([#48](https://github.com/yuyash/auto-forex-web-service/issues/48)) ([220238c](https://github.com/yuyash/auto-forex-web-service/commit/220238c7497cb7f0602c1ba3b7d567bd3c657d29))
* **events:** enforce 1:1 canonical floor strategy events across backend+frontend ([4af619a](https://github.com/yuyash/auto-forex-web-service/commit/4af619a14a102916aad7a0ddde6e84a0573c67aa))
* **execution:** make reruns create executions + improve logs; hide non-layer chart labels. ([e1c96e5](https://github.com/yuyash/auto-forex-web-service/commit/e1c96e55f5817d5b9272078a95be5fde75b870a2))
* **floor:** default momentum to candle lookback ([d5b5f9c](https://github.com/yuyash/auto-forex-web-service/commit/d5b5f9c17921938ff624a94ef849aaa1e01299dd))
* hedging and trend panel ([#85](https://github.com/yuyash/auto-forex-web-service/issues/85)) ([8743b6a](https://github.com/yuyash/auto-forex-web-service/commit/8743b6ac2edf51f429039edb705dcbd8a2555154))
* improve market task logging ([#100](https://github.com/yuyash/auto-forex-web-service/issues/100)) ([3512d2d](https://github.com/yuyash/auto-forex-web-service/commit/3512d2dbcf3ac9a85561f734d29b2e03bbf5e3a8))
* refresh token security ([#51](https://github.com/yuyash/auto-forex-web-service/issues/51)) ([4eb53b4](https://github.com/yuyash/auto-forex-web-service/commit/4eb53b4bd67af15ffa5a9d3a6fc695e28612058f))
* snowball strategy tab design ([#137](https://github.com/yuyash/auto-forex-web-service/issues/137)) ([ef21bc0](https://github.com/yuyash/auto-forex-web-service/commit/ef21bc0b3f97b40f70722f4d937c57de6b67a513))
* **trading:** add planned_exit_price_formula to strategy events and … ([#96](https://github.com/yuyash/auto-forex-web-service/issues/96)) ([13c0a1b](https://github.com/yuyash/auto-forex-web-service/commit/13c0a1b3263f4b01a2d578bf7e21edda67afaebd))
* **trading:** add planned_exit_price_formula to strategy events and improve mobile UI ([13c0a1b](https://github.com/yuyash/auto-forex-web-service/commit/13c0a1b3263f4b01a2d578bf7e21edda67afaebd))
* **trading:** enforce page/page_size pagination across logs & results endpoints ([2d66aad](https://github.com/yuyash/auto-forex-web-service/commit/2d66aad0f6b9b40f133fff5e5ae42388fbeb1f90))
* **trading:** improve trading system with enhanced events, positions, and UI components ([a356dad](https://github.com/yuyash/auto-forex-web-service/commit/a356dad5618639968719328f4ae257e843568838))
* **trading:** improve trading system with enhanced events, positions… ([#91](https://github.com/yuyash/auto-forex-web-service/issues/91)) ([a356dad](https://github.com/yuyash/auto-forex-web-service/commit/a356dad5618639968719328f4ae257e843568838))
* **trading:** improve trading UI and backend execution handling ([#93](https://github.com/yuyash/auto-forex-web-service/issues/93)) ([48ebe50](https://github.com/yuyash/auto-forex-web-service/commit/48ebe50cf5015546d37629ce32fa10b1f0011e46))
* **trading:** persist live execution artifacts + metrics checkpoints ([a6b8c8d](https://github.com/yuyash/auto-forex-web-service/commit/a6b8c8d1516a42b171b4dac8a688f489274eae88))
* **trading:** refactor app structure ([#21](https://github.com/yuyash/auto-forex-web-service/issues/21)) ([6e5db34](https://github.com/yuyash/auto-forex-web-service/commit/6e5db3461377af6596b6e1e5c6b8ce4c5df1eddb))


### Bug Fixes

* add version info ([#27](https://github.com/yuyash/auto-forex-web-service/issues/27)) ([b5217d1](https://github.com/yuyash/auto-forex-web-service/commit/b5217d16a4e476825b5521db9fe1d53c2fe9093a))
* api enhancement ([#40](https://github.com/yuyash/auto-forex-web-service/issues/40)) ([ab0b564](https://github.com/yuyash/auto-forex-web-service/commit/ab0b564dd6589279ed84556ba586d64e01dfb60d))
* **auth:** add AnonRateThrottle to protect unauthenticated endpoints ([#56](https://github.com/yuyash/auto-forex-web-service/issues/56)) ([ae490ce](https://github.com/yuyash/auto-forex-web-service/commit/ae490ce1128b01d2b143c90f98570adc8780dae1))
* **backtest:** make charts and markers robust ([25013aa](https://github.com/yuyash/auto-forex-web-service/commit/25013aa50742b17feb59d019843ac4a32d2b2f8c))
* celery task doesnt update the progress correctly. ([f14f3f2](https://github.com/yuyash/auto-forex-web-service/commit/f14f3f202d459ea599bea27ce89155b6a5e5db59))
* celery task race condition ([#31](https://github.com/yuyash/auto-forex-web-service/issues/31)) ([87b3354](https://github.com/yuyash/auto-forex-web-service/commit/87b33548f2cb0c52ad1aa4a2b250944ec8e707da))
* **chart:** fixed an issue where OHLC chart doesn't follow the progre… ([#120](https://github.com/yuyash/auto-forex-web-service/issues/120)) ([777df1c](https://github.com/yuyash/auto-forex-web-service/commit/777df1c423701179c8b79f96ed1b1575de8cd844))
* **chart:** fixed an issue where OHLC chart doesn't follow the progress bar properly. ([777df1c](https://github.com/yuyash/auto-forex-web-service/commit/777df1c423701179c8b79f96ed1b1575de8cd844))
* **chart:** trading migration 0019 ([#116](https://github.com/yuyash/auto-forex-web-service/issues/116)) ([a8d9a4e](https://github.com/yuyash/auto-forex-web-service/commit/a8d9a4e7d931c2106f4b643bef05a70f6e7e133c))
* clear stale stream cache on startup ([cc65f57](https://github.com/yuyash/auto-forex-web-service/commit/cc65f57a8190bf7ab95151984b07515783eb959b))
* **docker:** prevent prod config bind-mount shadowing Django settings. ([b3270b1](https://github.com/yuyash/auto-forex-web-service/commit/b3270b1b11bfd83869950037656d8cd752eb04ce))
* enforce frontend npm ci and override blocked react-is ([#46](https://github.com/yuyash/auto-forex-web-service/issues/46)) ([1f200b4](https://github.com/yuyash/auto-forex-web-service/commit/1f200b475d5bedc8de79256ec03b19f5a651c877))
* **floor-strategy:** reset retracement flag when price continues moving against position ([e88207b](https://github.com/yuyash/auto-forex-web-service/commit/e88207bc09c890e6f575696c7a49416048838caa))
* handle immutable ExecutionMetrics for trading tasks ([9a39233](https://github.com/yuyash/auto-forex-web-service/commit/9a392333e83ec398185ec5754a67825778c1f127))
* Handle new OANDA API message types for streaming ([47f7d25](https://github.com/yuyash/auto-forex-web-service/commit/47f7d2504b39648f87561f07483255229bbefa13))
* incremental polling reduce backend load ([#24](https://github.com/yuyash/auto-forex-web-service/issues/24)) ([980f163](https://github.com/yuyash/auto-forex-web-service/commit/980f1637145586a6955bfdb434532fcd1ed1b3e7))
* limit live results and strategy events to prevent 1GB+ JSON payloads ([61c4477](https://github.com/yuyash/auto-forex-web-service/commit/61c4477ea1f1fc846f08ea3207185e420c5a623e))
* **logging:** improve production logging ([#106](https://github.com/yuyash/auto-forex-web-service/issues/106)) ([06f2fdb](https://github.com/yuyash/auto-forex-web-service/commit/06f2fdb068dda50fba59a72312a3be4e11bf4940))
* **market-data:** use correct OANDA streaming hostname. ([af6e392](https://github.com/yuyash/auto-forex-web-service/commit/af6e39257d6a25f99bac766deeca239a318a39dc))
* **market:** dedupe TickData bulk upserts to avoid Postgres cardinality violation ([397a45c](https://github.com/yuyash/auto-forex-web-service/commit/397a45c44561af2636297d6b2b6295f35488b400))
* **metrics:** resolve overlay display and add viewport-driven fetching ([#114](https://github.com/yuyash/auto-forex-web-service/issues/114)) ([e87a285](https://github.com/yuyash/auto-forex-web-service/commit/e87a2855b4ccf087d42cf4d4f876a48c73737a24))
* **orders:** change broker_order_id from CharField(255) to TextField ([#104](https://github.com/yuyash/auto-forex-web-service/issues/104)) ([8f16ec6](https://github.com/yuyash/auto-forex-web-service/commit/8f16ec6a76955d4b4fc26488dfe75b71aaa78534))
* prevent retracement_limit_reached spam generating 167K+ events ([6c14968](https://github.com/yuyash/auto-forex-web-service/commit/6c149681e55eee083914f78a2acca8f625e3a2cc))
* read version from pyproject.toml instead of importlib.metadata ([#29](https://github.com/yuyash/auto-forex-web-service/issues/29)) ([8a8f986](https://github.com/yuyash/auto-forex-web-service/commit/8a8f986a5c5ae0433cb8c5ca24c339f13e4d29ad))
* reduce API rate limit pressure and lazy-load chart data ([#38](https://github.com/yuyash/auto-forex-web-service/issues/38)) ([e733834](https://github.com/yuyash/auto-forex-web-service/commit/e733834e6bf47bd144d98d9c526f5a5eceb19745))
* resolve all ty type checker errors and warnings ([#13](https://github.com/yuyash/auto-forex-web-service/issues/13)) ([1883525](https://github.com/yuyash/auto-forex-web-service/commit/1883525ce1fd5008b5c46d42e57d185620a78502))
* resolve flake8, mypy, and pylint errors in floor strategy and task executor ([b2b9949](https://github.com/yuyash/auto-forex-web-service/commit/b2b9949c5408ccbc163fdf92abd249b55f0ca88d))
* **security:** remove unused UserSession.last_activity field ([#112](https://github.com/yuyash/auto-forex-web-service/issues/112)) ([3198e40](https://github.com/yuyash/auto-forex-web-service/commit/3198e40782bf16ffe27a35c5e04c53854fb6f068))
* snowball add count reset and tests ([#73](https://github.com/yuyash/auto-forex-web-service/issues/73)) ([847ffd9](https://github.com/yuyash/auto-forex-web-service/commit/847ffd9cef2929009549f418acfb95541d11ea97))
* stabilize rerun/status flow and fix floor trade PnL metrics ([d7f2325](https://github.com/yuyash/auto-forex-web-service/commit/d7f23254fef3c23c2f79e48732ef255f68ca6219))
* stabilize streams, logs, and backtest/trading results UI ([f6f15a2](https://github.com/yuyash/auto-forex-web-service/commit/f6f15a241fda3c57ca995472e6de429e64b63ef5))
* **strategy:** correct snowball counter lot sizing and add retracemen… ([#87](https://github.com/yuyash/auto-forex-web-service/issues/87)) ([804e7d1](https://github.com/yuyash/auto-forex-web-service/commit/804e7d15754e8a6310dd3a03201ed805b1f327f2))
* **strategy:** guard m_pips range validation behind dynamic_tp_enable… ([#81](https://github.com/yuyash/auto-forex-web-service/issues/81)) ([b77df30](https://github.com/yuyash/auto-forex-web-service/commit/b77df30723c2fe1852601fb0c6198a8cdf428905))
* **strategy:** guard m_pips range validation behind dynamic_tp_enabled and raise m_pips_max default ([b77df30](https://github.com/yuyash/auto-forex-web-service/commit/b77df30723c2fe1852601fb0c6198a8cdf428905))
* **strategy:** normalize atr_timeframe to uppercase and add snowball … ([#75](https://github.com/yuyash/auto-forex-web-service/issues/75)) ([2c7995c](https://github.com/yuyash/auto-forex-web-service/commit/2c7995c50ad7582732cbcbfb1ec3efa559b6405c))
* **strategy:** normalize atr_timeframe to uppercase and add snowball tests ([2c7995c](https://github.com/yuyash/auto-forex-web-service/commit/2c7995c50ad7582732cbcbfb1ec3efa559b6405c))
* **tests:** update expected hostnames for streaming tests ([cbaa7a2](https://github.com/yuyash/auto-forex-web-service/commit/cbaa7a27039043ae9687813829ced34e0ccf33fe))
* **trading:** trading task creation ([#125](https://github.com/yuyash/auto-forex-web-service/issues/125)) ([74f1dbd](https://github.com/yuyash/auto-forex-web-service/commit/74f1dbd177acef2936fd8d0a1245c93c58a84be2))
* **trading:** use pure arithmetic in planned_exit_price_formula ([#98](https://github.com/yuyash/auto-forex-web-service/issues/98)) ([0b5edbd](https://github.com/yuyash/auto-forex-web-service/commit/0b5edbdeb05c6fc0fab1be041bbee75fb4cc3011))
* Use decrypted API token for OANDA streaming connections ([aa9ead5](https://github.com/yuyash/auto-forex-web-service/commit/aa9ead51e80b0930655e71f54b60f5dba5c0bbd9))
* vscode settings warnings ([#134](https://github.com/yuyash/auto-forex-web-service/issues/134)) ([c55842d](https://github.com/yuyash/auto-forex-web-service/commit/c55842d4b25147605c7e480afe08a2259d6cf728))
