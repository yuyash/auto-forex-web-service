# SnowballNet Strategy 実装仕様

## 1. 目的

SnowballNet は、両建て不可かつ FIFO 制約を受ける OANDA US 口座向けの Snowball 派生戦略である。
既存 Snowball のように個別建玉、両建てサイクル、グリッドスロットを前提にせず、同一通貨ペアの単一ネット建玉を管理単位とする。

## 2. 基本方針

- 取引方向は設定で `long`、`short`、または `auto` を選ぶ。`auto` は新しいネット建玉を開始するときに EMA トレンドで方向を決める。
- 建玉追加は既存ポジションにマージし、DB 上も平均注文価格の単一ポジションとして扱う。
- 判断基準は個別建玉価格ではなく、ネット建玉の平均注文価格である。
- LONG の場合、現在の買い側価格が平均注文価格から一定 pips 逆行すると増し玉し、売り側価格が平均注文価格から一定 pips 有利に進むと部分決済する。
- SHORT の場合は上記を反転する。
- ロスカット設定を有効にした場合、平均注文価格からの Pips 差が損失側しきい値を超えるとネット建玉を全決済し、次の Tick から初回エントリーとして再開する。デフォルトは OFF、しきい値のデフォルトは 100 pips。
- 決済は OANDA trade ID ではなく instrument のネットポジション決済として実行できるようにし、FIFO/非ヘッジ口座で個別 trade close に依存しない。

## 3. 状態

`ExecutionState.strategy_state` には以下を保持する。

| フィールド         | 説明                                                                                                  |
| ------------------ | ----------------------------------------------------------------------------------------------------- |
| `direction`        | `long` / `short` / `auto`。`auto` は方向判定待ち、`long` / `short` は現在のネット建玉に使う確定方向。 |
| `direction_mode`   | 固定方向か自動方向か。                                                                                |
| `auto_direction_*` | 自動方向判定用の EMA、サンプル数、直近の判定結果。                                                    |
| `net_units`        | 現在のネット建玉数量。                                                                                |
| `average_price`    | ネット建玉の平均注文価格。                                                                            |
| `position_id`      | DB 上の単一オープンポジション ID。                                                                    |
| `add_count`        | 平均注文価格基準で実行済みの増し玉回数。                                                              |
| `pending_action`   | 発注済みで約定反映待ちの action。重複発注防止に使う。                                                 |
| `metrics`          | UI/API 用の平均注文価格、現在価格、Pips差、次回増し玉距離など。                                       |

## 4. 売買ロジック

### 4.1 初回エントリー

`net_units <= 0` または未初期化なら `initial_lot_size * base_units` を現在価格で発注する。
`trade_direction=auto` の場合は、短期 EMA と長期 EMA の差を使って方向を判定する。
設定したウォームアップ Tick 数に達するまでは建玉せず待機する。
ウォームアップ後、短期 EMA と長期 EMA の差を pips 換算し、差が `auto_direction_threshold_pips` 以上なら買い、`-auto_direction_threshold_pips` 以下なら売りとする。
差がしきい値内の場合は中立として建玉せず、次の Tick で再判定する。
全てのネット建玉がクローズされた後も、次の初回エントリーでは同じ判定を再実行する。
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

`adverse_pips >= add_interval_pips` かつ `max_add_count` / `max_net_units` の上限内なら増し玉する。
増し玉数量は `add_lot_size * base_units` を基本とし、`effective_max_net_units` までの残り数量がそれ未満なら残り数量に丸める。
約定後の平均注文価格は加重平均で更新する。

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
部分決済後の平均注文価格は変わらず、ネット数量だけが減る。

### 4.4 証拠金保護

証拠金精算割合は Tick ごとの metrics から取得し、割合ベースの保護判定に使う。
判定順序は、未反映の発注がない場合に、緊急停止、初回エントリー、ロスカット、証拠金縮小、利確、増し玉の順である。

`emergency_enabled=true` の場合、証拠金精算割合が `emergency_threshold_pct` 以上になると、StrategyResult は `should_stop=true` としてタスクをエラー停止する。
この緊急停止は決済イベントを発行せず、運用者が状態と口座を確認するための停止である。

`margin_reduce_enabled=true` の場合、証拠金精算割合が `margin_reduce_threshold_pct` 以上かつネット数量が初回数量を超えていれば、ネット建玉の一部を決済する。
決済数量は `margin_reduce_target_pct` に近づく数量を優先し、算出できない場合は `margin_reduce_ratio` を使う。
通常の部分決済と同様、`min_close_units` 未満の端数を残す場合は全決済する。

### 4.5 ロスカットと再開

`loss_cut_enabled=true` の場合、平均注文価格からの Pips 差が `-loss_cut_threshold_pips` 以下になった時点で、現在のネット建玉を全決済する。
全決済の約定反映後は `net_units=0`、`average_price=None`、`add_count=0` に戻し、次の Tick では初回エントリーと同じ流れで再開する。
`trade_direction=auto` の場合は、この再開時にも方向判定を再実行する。

## 5. UI/API

SnowballNet では Position タブを非表示にする。
Strategy タブは Snowball のサイクル/グリッド表示ではなく、`strategy/net-chart` API を使ったネット建玉チャートを表示する。

チャート API は以下を返す。

- OHLC: OANDA candle API から取得した指定 `granularity` のローソク足。TradingTask は紐づく OANDA アカウント、BacktestTask はユーザーのデフォルト OANDA アカウントを使う。
- price lines: 平均注文価格、決済価格、次回増し玉価格。次回増し玉が上限などで実行できない場合は、理論上の次回増し玉価格をドット線で表示する。
- oscillator lines: ネットポジション数、平均注文価格からの pips 差、ロスカットしきい値、証拠金精算割合、実現損益、未実現損益、証拠金縮小しきい値、縮小目標率、緊急停止しきい値。
- markers: 注文と決済。`merge_markers=true` のときは granularity bucket ごとに集約する。
- current: 現在のネット数量、平均注文価格、現在価格、pips差、実現損益、未実現損益、pending action。

フロントエンドでは follow mode を持つ。
デフォルトは follow mode 有効、`M1` granularity で、現在 tick を X 軸中央に置き、前後約 1 日ずつ、合計約 2 日の時間窓を表示する。
表示範囲を指定する場合、ローソク足・マーカーの過大ロードを避けるため、選択可能な `granularity` は時間範囲に応じて制限する。
上限は `granularity_seconds * 20160` 秒の範囲で、例えば `M1` は 2 週間まで、`M5` は 10 週間までである。
フロントエンドは範囲に対して細かすぎる粒度を無効化し、Auto または現在選択中の粒度が範囲に合わない場合は許容される最も細かい粒度に切り替える。
バックエンドの `strategy/net-chart` API も同じ上限を検証し、上限を超える範囲は ValidationError とする。
右側の価格軸には現在価格に加えて、平均注文価格、決済価格、次回増し玉価格の意味付きラベルを表示する。
ネットポジション数、証拠金精算割合、実現損益、未実現損益、平均注文価格からの Pips 差、平均注文価格、決済価格、次回増し玉価格は、OHLC とは別のラインチャートとしても表示する。
平均注文価格からの Pips 差チャートには、有効時のみロスカットしきい値を負の水平ラインとして表示する。
証拠金精算割合チャートには、証拠金縮小機能が有効な場合は縮小開始率と縮小目標率を、緊急停止が有効な場合は緊急停止しきい値を水平ラインとして表示する。
チャート設定ダイアログでは、OHLC、ネットポジション数、Pips、証拠金精算割合、損益、平均注文価格、決済価格、次回増し玉価格の各チャートの表示・非表示を切り替えられる。
OHLC チャートでは、注文マーカー、現在 Tick ライン、価格ライン、証拠金精算割合オーバーレイ、SMA/EMA、ボリンジャーバンド、出来高の表示・非表示を個別に切り替えられる。
週末など OANDA candle API がローソク足を返さない連続区間は、チャート上に `No Data` の帯として表示する。
follow mode 中は現在 tick を X 軸中央に置く。
ユーザーがスクロールした場合は follow mode を解除し、以後のデータ更新ではチャートの表示位置を動かさない。
Follow ボタンで再び現在 tick 中央へ戻る。
