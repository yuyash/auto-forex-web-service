## 1. 目的

- 両建てを基点に、順行側の小刻み利確（回転利確）でキャッシュを積み上げる。
- 逆行側はナンピン（カウンターエントリー）で平均取得価格を寄せ、直近取得分のみを段別決済して平均価格を押し下げる。
- 証拠金比率に応じて段階的に防御し、強制ロスカットを回避する。

## 2. 前提と記号

### 2.1 前提

- 両建て可能口座のみ（日本版 OANDA を想定）
- FIFO 制約なし（米国口座は対象外）
- 対象通貨: `USD_JPY`
- 1 pip = `0.01` 円
- 価格判定・トリガー判定・決済判定は `bid/ask` を使用
- 逆行距離の計測には `mid`（= (bid+ask)/2）を使用（スプレッド歪み回避）
- ヘッジ無効時は LONG のみで初期化（SHORT は建てない）

### 2.2 記号

- $P_{\text{avg}}=\dfrac{\sum_i p_i u_i}{\sum_i u_i}$
- $\mathrm{ratio}=\dfrac{\mathrm{required\_margin}}{\mathrm{NAV}}\times 100$（証拠金比率 %）
- NAV = 口座残高 + 未実現損益
- 証拠金計算: OANDA のMAX方式（LONG/SHORT の必要証拠金が多い方のみ）

### 2.3 用語

| 用語 | 説明 |
| --- | --- |
| サイクル | 1つの初期エントリーから完了までの一連のトレード群。LONG/SHORT それぞれ独立に管理される |
| グリッド | サイクル内の全ポジションを管理する統一構造。レイヤーのリストで構成される |
| レイヤー | グリッド内のリトレースメントスロット群。各レイヤーは R0（レイヤー初期）+ R1〜R(r_max) のスロットを持つ |
| スロット | レイヤー内の番号付き座席。エントリーを保持するか空の状態を取る |
| ヘッド | サイクル内の最も古いポジション（動的に決定）。ヘッドのTPがサイクル完了のトリガーとなる |
| カウンターエントリー | 逆行時にスロットに配置されるナンピンポジション（R1以降） |
| レイヤー初期エントリー | 新レイヤー開始時にR0に建てるエントリー（L2以降） |

### 2.4 パラメータ記号対応

| 記号 | パラメータ名 |
| --- | --- |
| $r_{\max}$ | `r_max` |
| $f_{\max}$ | `f_max` |
| $m_{\mathrm{pips}}$ | `m_pips` |
| $m_{\mathrm{th}}$ | `m_th` |
| $m1_{\mathrm{th}}$ | `m1_th` |
| $n_{\mathrm{th}}$ | `n_th` |
| $n_{\mathrm{head}}$ | `n_pips_head` |
| $n_{\mathrm{tail}}$ | `n_pips_tail` |
| $n_{\mathrm{flat}}$ | `n_pips_flat_steps` |
| $\gamma_n$ | `n_pips_gamma` |
| $\Delta t_{\mathrm{cool}}$ | `cooldown_sec` |

## 3. パラメータ

### 3.1 建玉・利確（コア）

| Key | 意味 | Default |
| --- | --- | --- |
| `base_units` | 基本ロット (通貨単位) | `1000` |
| `m_pips` | 順行側の利確幅 (pips) | `50` |
| `trend_lot_size` | 順行側エントリーのロット数（`base_units` に乗算） | `1` |
| `r_max` | 1レイヤーあたりのカウンタースロット数 | `7` |
| `f_max` | レイヤーの最大数 | `3` |
| `post_r_max_base_factor` | 新レイヤー作成時の `base_units` 倍率 | `1` |
| `refill_up_to` | 決済後に再建玉可能なスロット上限（R1〜R_n）。0=再建玉なし | `2` |
| `round_step_pips` | 間隔・TP計算値の丸め単位（pip） | `0.1` |

### 3.2 逆行側間隔（Interval Mode）

| `interval_mode` | 動作 |
| --- | --- |
| `constant` | 全段 `n_pips_head` 固定 |
| カーブ系 | `n_pips_head` → `n_pips_tail` へガンマカーブで遷移 |
| `manual` | `manual_intervals` 配列でユーザーが段ごとに指定 |

| Key | 意味 | Default | 表示条件 |
| --- | --- | --- | --- |
| `interval_mode` | 間隔モード | `constant` | 常時 |
| `n_pips_head` | 間隔初期値（pip） | `30` | `constant` / カーブ系 |
| `n_pips_tail` | 間隔終端値（pip） | `14` | カーブ系のみ |
| `n_pips_flat_steps` | 初期固定段数 | `2` | カーブ系のみ |
| `n_pips_gamma` | 減衰カーブ係数 | `1.4` | カーブ系のみ |
| `manual_intervals` | 段ごとのpip間隔配列（`r_max` 個） | `[]` | `manual` のみ |

### 3.3 逆行側決済（Counter TP Mode）

| `counter_tp_mode` | 動作 |
| --- | --- |
| `weighted_avg` | 同レイヤー内の全ポジションの加重平均価格を決済価格とする（デフォルト） |
| `fixed` | 全段 `counter_tp_pips` 固定 |
| `additive` | `counter_tp_pips + counter_tp_step_amount × (k-1)` |
| `subtractive` | `counter_tp_pips - counter_tp_step_amount × (k-1)`（下限 0.1） |
| `multiplicative` | `counter_tp_pips × counter_tp_multiplier^(k-1)` |
| `divisive` | `counter_tp_pips / counter_tp_multiplier^(k-1)`（下限 0.1） |

| Key | 意味 | Default | 表示条件 |
| --- | --- | --- | --- |
| `counter_tp_mode` | 決済価格モード | `weighted_avg` | 常時 |
| `counter_tp_pips` | 利確幅の基準値（pip） | `25` | `weighted_avg` 以外 |
| `counter_tp_step_amount` | 段階増減量（pip） | `2.5` | `additive` / `subtractive` |
| `counter_tp_multiplier` | 段階乗数 | `1.2` | `multiplicative` / `divisive` |

### 3.4 ストップロス

| Key | 意味 | Default |
| --- | --- | --- |
| `stop_loss_enabled` | ストップロスの有効/無効 | `false` |
| `reseed_on_all_pending` | 全サイクルが再建待ちの場合に新サイクルを作成 | `false` |

### 3.5 証拠金保護

| Key | 意味 | Default | 表示条件 |
| --- | --- | --- | --- |
| `shrink_enabled` | 縮小モードの有効/無効 | `true` | 常時 |
| `m_th` | 縮小開始の証拠金比率（%） | `70` | 縮小有効時 |
| `m1_th` | 縮小の目標証拠金比率（%） | `50` | 縮小有効時 |
| `lock_enabled` | ロックモードの有効/無効 | `true` | 常時 |
| `n_th` | ロック開始の証拠金比率（%） | `85` | ロック有効時 |
| `cooldown_sec` | ロック解除後の再開待機（秒） | `300` | ロック有効時 |
| `emergency_enabled` | 緊急停止の有効/無効 | `true` | 常時 |

### 3.6 バリデーション

- `shrink_enabled` かつ `lock_enabled` のとき: $m_{\mathrm{th}} < n_{\mathrm{th}} < 100$
- `shrink_enabled` のとき: $0 < m1_{\mathrm{th}} < m_{\mathrm{th}} < 100$
- `lock_enabled` のとき: $0 < n_{\mathrm{th}} < 100$
- $n_{\mathrm{head}} \ge n_{\mathrm{tail}} > 0$
- $n_{\mathrm{flat}} < r_{\max}$
- `counter_tp_mode` が `weighted_avg` 以外のとき: $\mathrm{counter\_tp\_pips} > 0$
- `interval_mode` が `manual` のとき: `manual_intervals` の要素数 = `r_max`、全値 ≥ 1
- $0 \le \mathrm{refill\_up\_to} < r_{\max}$
- `stop_loss_enabled` と `shrink_enabled` は同時に有効にできない

## 4. サイクルとグリッドの構造

### 4.1 統一グリッド

各サイクルは `PositionGrid` を持ち、全ポジション（初期エントリー含む）がグリッド内のスロットに配置される。

```
Cycle
├── direction: LONG | SHORT
├── status: ACTIVE | PENDING | COMPLETED
├── grid: PositionGrid
│   └── layers[]
│       ├── Layer 1 (L1)
│       │   ├── R0: 初期エントリー（サイクルヘッド候補）
│       │   ├── R1: カウンター 1
│       │   ├── R2: カウンター 2
│       │   └── ... R(r_max)
│       ├── Layer 2 (L2)
│       │   ├── R0: レイヤー初期エントリー
│       │   ├── R1: カウンター 1
│       │   └── ...
│       └── Layer 3 (L3) ...
├── counter_close_count: int
└── stop_loss_pending_rebuilds[]  ← StrategyState レベルで管理
```

### 4.2 サイクルヘッド（動的）

サイクルヘッドは「グリッド内の最も古いポジション」として動的に決定される。具体的には、レイヤーを L1 から順に走査し、最初に見つかった occupied スロットのエントリーがヘッドとなる。

ヘッドのTPがサイクル完了のトリガーとなる。ヘッドのTP = entry_price ± m_pips × pip_size。

### 4.3 スロットの状態遷移

各スロットは以下の状態を取る:

| 状態 | entry | ever_closed | 説明 |
| --- | --- | --- | --- |
| 空・未使用 | None | false | エントリーを配置可能 |
| 使用中 | Entry | - | エントリーが保持されている |
| 空・再建玉可能 | None | false | クローズされたが再利用可能（refill_up_to 以下、またはSL再建待ち） |
| 空・sealed | None | true | 再利用不可。次の逆行で新レイヤーが必要 |

クローズ時の `ever_closed` 設定:

- 通常のTPクローズ: スロット番号 ≤ `refill_up_to` → `false`（再建玉可能）、それ以外 → `true`（sealed）
- ストップロスクローズ: 常に `false`（再建待ちとして扱う）
- レイヤー初期エントリー（R0）のクローズ: `true`（レイヤー除去）

### 4.4 サイクルのステータス

| ステータス | 説明 |
| --- | --- |
| ACTIVE | 通常稼働中 |
| PENDING | グリッドが空だがSL再建待ちのエントリーがある。再建されたら ACTIVE に復帰 |
| COMPLETED | サイクル完了。新サイクルが作成される |

## 5. 順行側ロジック（回転利確）

### 5.1 初期化

戦略開始時:

- ヘッジ有効時: LONG サイクルと SHORT サイクルを同時に作成
- ヘッジ無効時: LONG サイクルのみ作成

各サイクルは L1/R0 に初期エントリーを建玉。TP = entry ± m_pips × pip_size。

### 5.2 利確と再エントリー

ヘッドのTPがヒットしたらサイクル完了:

- LONG: $bid \ge entry\_price + m_{\mathrm{pips}} \times pip\_size$
- SHORT: $ask \le entry\_price - m_{\mathrm{pips}} \times pip\_size$

ヘッドTP到達時の処理:

1. グリッド内に他のエントリーが残っていないか確認
2. 残っている場合、全エントリーのTPが同一ティックで到達しているか確認
   - 全到達: 全エントリーをフラッシュクローズしてからヘッドをクローズ
   - 未到達あり: close order violation（戦略停止）
3. ヘッドをクローズ
4. 同方向で新サイクルを作成

### 5.3 サイクル再シード

全サイクルが COMPLETED になった方向は、自動的に新サイクルを作成。

`reseed_on_all_pending=true` の場合、全サイクルが PENDING（SL再建待ち）の方向でも新サイクルを作成し、再建を待ちながら取引を継続する。

## 6. 逆行側ロジック（カウンターエントリー）

### 6.1 カウンター追加の前提条件

1. サイクルが ACTIVE
2. ヘッドが含み損状態
3. 同一ティック内でカウンターTPクローズが発生していない

### 6.2 スロット配置の判定

現在のレイヤーの `next_available_counter_slot()` を確認:

- 空きスロットあり → 逆行距離が閾値に達していればエントリーを配置
- 空きスロットなし（`needs_new_layer=true`）→ 新レイヤーを作成（セクション8参照）

`next_available_counter_slot()` は R1 から順に走査し:
- `is_available`（空・未使用）なスロットを返す
- `is_empty and ever_closed`（sealed）なスロットに到達したら `None` を返す（新レイヤーが必要）

SLクローズされたスロットは `ever_closed=false` のため sealed とは見なされず、再建待ちとして「存在する」扱いになる。

### 6.3 逆行距離の計測

- レイヤー内にカウンターエントリーがない場合: R0（レイヤー初期エントリー）からの距離
- レイヤー内にカウンターエントリーがある場合: 最も高いR番号のエントリーからの距離

距離は `mid` 価格で計測。

### 6.4 ロットサイズ

$lot = (slot\_index + 1) \times layer\_base\_units$

### 6.5 決済価格の計算

`weighted_avg` モード: 同レイヤー内の全ポジション（R0含む）と新エントリーの加重平均価格。

その他のモード: エントリー価格 ± `counter_tp_pips(k)` × pip_size。新エントリー追加時に既存エントリーのTPも再計算。

## 7. 決済ロジック

### 7.1 カウンターTPクローズ

最新レイヤーから逆順に走査し、最も高いR番号の occupied スロットのTPがヒットしていればクローズ。1ティックにつき最大1件。

クローズ後:
- スロット番号 ≤ `refill_up_to`: `ever_closed=false`（再建玉可能）
- スロット番号 > `refill_up_to`: `ever_closed=true`（sealed）

### 7.2 レイヤー初期エントリー（R0）の決済

L2以降のレイヤーで全カウンタースロットが空になり、R0だけが残った場合、R0のTPがヒットしていればクローズしてレイヤーを除去。

### 7.3 TP判定

- LONG: $bid \ge close\_price$
- SHORT: $ask \le close\_price$

## 8. レイヤー進行

### 8.1 新レイヤー作成の条件

`needs_new_layer=true`（全スロット使用済み、または sealed スロットに到達）かつ:

1. レイヤー数 < `f_max + 1`
2. ヘッドが含み損状態
3. 前レイヤーの最も高いR番号のエントリーから所定の逆行距離に達している

### 8.2 レイヤー初期エントリーのTP

`layer_initial_close_price` により、前レイヤーの `highest_occupied_slot` の `close_price` をコピーする。前レイヤーにカウンターが残っていない場合は R0 の TP がコピーされる。

フォールバック（前レイヤーに occupied スロットがない場合）: entry ± m_pips × pip_size。

## 9. ストップロスと再建

### 9.1 ストップロス価格の計算

各エントリーの建玉時に SL 価格が設定される。計算式:

1. $tp\_pips = |close\_price - entry\_price| / pip\_size$
2. $next\_entry\_price = entry\_price \mp next\_interval\_pips \times pip\_size$（LONGなら-、SHORTなら+）
3. $tp\_pips < next\_interval\_pips$ の場合: $SL = next\_entry\_price$
4. $tp\_pips \ge next\_interval\_pips$ の場合: $SL = next\_entry\_price \mp next\_interval\_pips \times pip\_size$

### 9.2 ストップロスクローズ

各ティックで全エントリーの SL をチェックし、ヒットした全エントリーを一括クローズ:

- LONG: $bid \le stop\_loss\_price$
- SHORT: $ask \ge stop\_loss\_price$

クローズ時の処理:

1. `StopLossClosedEntry` として `stop_loss_pending_rebuilds` に記録（元の position_id を含む）
2. スロットを `refillable=true` でクローズ（`ever_closed=false` を維持）
3. `ClosePositionEvent` を発行（`close_reason="stop_loss"`）

スロットが `refillable=true` でクローズされるため、グリッド上は「存在する」扱いのまま。これにより:
- `needs_new_layer` が不要に `true` にならない
- 不要なレイヤー追加が防止される
- TP順序の逆転が防止される

### 9.3 ストップロス再建

各ティックで `stop_loss_pending_rebuilds` をチェックし、価格が元のエントリー価格に戻ったエントリーを再建:

- LONG: $bid \ge entry\_price$
- SHORT: $ask \le entry\_price$

再建時の処理:

1. 元のスロットが空で occupied でないことを確認
2. 新しい `Entry` を作成（元と同じパラメータ、`is_rebuild=true`）
3. 元のエントリー価格で再建（`entry_price` を上書き）
4. SL を再計算
5. スロットに配置（`ever_closed=false` にリセット）
6. `RebuildPositionEvent` を発行（`original_position_id` を含む）
7. DB上の元の Position レコードを再オープン（新規レコードは作成しない）

### 9.4 サイクルの PENDING ステータス

SLクローズによりグリッドが空になった場合:

- `stop_loss_pending_rebuilds` に該当サイクルのエントリーがある → PENDING
- ない → COMPLETED

PENDING サイクルは再建が実行されると ACTIVE に復帰する。

### 9.5 `reseed_on_all_pending`

有効時、ある方向の全サイクルが PENDING の場合、新サイクルを作成して取引を継続する。再建待ちのサイクルは並行して再建を待つ。

## 10. 証拠金保護

### 10.1 保護レベル一覧

| レベル | 条件 | 有効/無効 |
| --- | --- | --- |
| NORMAL | 全閾値未満 | - |
| SHRINK | `ratio >= m_th` | `shrink_enabled` |
| LOCKED | `ratio >= n_th` | `lock_enabled` |
| EMERGENCY | `ratio >= 95` | `emergency_enabled` |

### 10.2 縮小モード（`ratio >= m_th`）

1. 新規エントリーとカウンター追加を停止
2. 全アクティブサイクルから含み損が最も大きいエントリーを1つクローズ
3. `ratio < m1_th` まで通常モードへ戻さない

縮小で全ポジションがクローズされても `ratio` が `m1_th` を下回らない場合、戦略を停止する。

### 10.3 ロックモード（`ratio >= n_th`）

ロック開始:

1. LONG/SHORT のネットエクスポージャを計算
2. 差分をヘッジエントリーで相殺（ネット0に）
3. 全ての新規/カウンター追加を禁止

ロック解除条件（全て満たす）:

1. `ratio < m1_th`
2. `cooldown_sec` 経過

解除後: ヘッジエントリーをクローズし、ratio に応じて縮小モードまたは通常モードへ復帰。

### 10.4 緊急停止（`ratio >= 95`）

戦略を即座に停止。ポジションの自動クローズは行わない。

## 11. tick 処理フロー

各 tick で以下の順序で処理される。保護系の処理が発生した場合はそこで return する。

1. NAV 更新（口座残高 + 全エントリーの未実現損益）
2. 証拠金比率の計算
3. 緊急停止チェック（`ratio >= 95` → 即停止）
4. ロック開始チェック（`ratio >= n_th` → ヘッジ追加して return）
5. ロック中の解除チェック（解除条件を満たせばヘッジ解消して return）
6. 縮小モードチェック（`ratio >= m_th` → 最大損失エントリーをクローズして return）
7. 通常モード復帰
8. 初期化（未初期化の場合、サイクル作成して return）
9. アクティブサイクルごとに以下を順次実行:
   1. カウンターTPクローズ（最新レイヤーの最大R番号から、1件/tick）
   2. ヘッドTPチェック（到達時はフラッシュ＆再エントリー）
   3. ストップロスクローズ（SLヒットした全エントリーを一括クローズ）
   4. ストップロス再建（価格が戻ったエントリーを再建）
   5. カウンター追加（9-1 でクローズが発生した場合はスキップ）
   6. サイクル完了判定（グリッド空 → PENDING or COMPLETED）
10. サイクル再シード（全 COMPLETED / 全 PENDING の方向に新サイクル作成）

## 12. イベント体系

| イベント | 説明 | 発行タイミング |
| --- | --- | --- |
| `OpenPositionEvent` | 新規ポジション作成 | 初期エントリー、カウンター追加、レイヤー初期エントリー |
| `ClosePositionEvent` | ポジション決済 | TP、SL、縮小、ロックヘッジ解消 |
| `RebuildPositionEvent` | SL後のポジション再建 | SL再建時（元の Position を再オープン） |

`ClosePositionEvent` の `close_reason`:

| close_reason | 説明 |
| --- | --- |
| `tp` | サイクルヘッドの利確 |
| `counter_tp` | カウンターエントリーの利確 |
| `layer_initial_tp` | レイヤー初期エントリーの利確 |
| `stop_loss` | ストップロス |
| `shrink` | 縮小プロテクション |
| `lock_hedge_open` | ロックヘッジ開始 |
| `lock_hedge_neutralize` | ロックヘッジ解消 |
