# SnowballNet Strategy 実装仕様

## 1. 目的

SnowballNet は、両建て不可かつ FIFO 制約を受ける OANDA US 口座向けの Snowball 派生戦略である。
既存 Snowball のように個別建玉、両建てサイクル、グリッドスロットを前提にせず、同一通貨ペアの単一ネット建玉を管理単位とする。

## 2. 基本方針

- 取引方向は設定で `long` または `short` のどちらか一方向を選ぶ。
- 建玉追加は既存ポジションにマージし、DB 上も平均建値の単一ポジションとして扱う。
- 判断基準は個別建玉価格ではなく、ネット建玉の平均建値である。
- LONG の場合、現在の買い側価格が平均建値から一定 pips 逆行すると増し玉し、売り側価格が平均建値から一定 pips 有利に進むと部分決済する。
- SHORT の場合は上記を反転する。
- 決済は OANDA trade ID ではなく instrument のネットポジション決済として実行できるようにし、FIFO/非ヘッジ口座で個別 trade close に依存しない。

## 3. 状態

`ExecutionState.strategy_state` には以下を保持する。

| フィールド       | 説明                                                        |
| ---------------- | ----------------------------------------------------------- |
| `direction`      | `long` / `short`。                                          |
| `net_units`      | 現在のネット建玉数量。                                      |
| `average_price`  | ネット建玉の平均建値。                                      |
| `position_id`    | DB 上の単一オープンポジション ID。                          |
| `add_count`      | 平均建値基準で実行済みの増し玉回数。                        |
| `pending_action` | 発注済みで約定反映待ちの action。重複発注防止に使う。       |
| `metrics`        | UI/API 用の平均建値、現在価格、Pips差、次回増し玉距離など。 |

## 4. 売買ロジック

### 4.1 初回エントリー

`net_units <= 0` または未初期化なら `initial_lot_size * base_units` を現在価格で発注する。
約定後、`average_price` と `position_id` を約定結果から確定する。

### 4.2 増し玉

次の増し玉段数を `add_count + 1` とし、`interval_mode` と `n_pips_*` または `manual_intervals` から必要逆行距離を計算する。

LONG:

```text
adverse_pips = (average_price - ask) / pip_size
```

SHORT:

```text
adverse_pips = (bid - average_price) / pip_size
```

`adverse_pips >= add_interval_pips` かつ `max_add_count` / `max_net_units` の上限内なら、`add_lot_size * base_units` を追加する。
約定後の平均建値は加重平均で更新する。

### 4.3 部分決済

LONG:

```text
favorable_pips = (bid - average_price) / pip_size
```

SHORT:

```text
favorable_pips = (average_price - ask) / pip_size
```

`favorable_pips >= take_profit_pips` なら、現在ネット数量の `partial_close_ratio` を目安に決済する。
ただし `min_close_units` を下回る端数を残す場合は全決済する。
部分決済後の平均建値は変わらず、ネット数量だけが減る。

## 5. UI/API

SnowballNet では Position タブを非表示にする。
Strategy タブは Snowball のサイクル/グリッド表示ではなく、`strategy/net-chart` API を使ったネット建玉チャートを表示する。

チャート API は以下を返す。

- OHLC: OANDA candle API から取得した指定 `granularity` のローソク足。TradingTask は紐づく OANDA アカウント、BacktestTask はユーザーのデフォルト OANDA アカウントを使う。
- price lines: 平均建値、利確価格、次回増し玉価格。
- oscillator lines: 平均建値からの pips 差、証拠金率。
- markers: 注文と決済。`merge_markers=true` のときは granularity bucket ごとに集約する。
- current: 現在のネット数量、平均建値、現在価格、pips差、pending action。

フロントエンドでは follow mode を持つ。
デフォルトは `H1` granularity で、現在 tick の前後約 250 本、合計約 500 本の時間窓を表示する。
週末など OANDA candle API がローソク足を返さない連続区間は、チャート上に `No Data` の帯として表示する。
follow mode 中は現在 tick を X 軸中央に置く。
ユーザーがスクロールした場合は follow mode を解除し、以後のデータ更新ではチャートの表示位置を動かさない。
Follow ボタンで再び現在 tick 中央へ戻る。
