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

（パラメータセクションは変更なし — セクション3.1〜3.6は省略。前バージョンと同一。）

## 4. サイクルとグリッドの構造

### 4.1 統一グリッド

各サイクルは `PositionGrid` を持ち、全ポジション（初期エントリー含む）がグリッド内のスロットに配置される。

```
Cycle
├── direction: LONG | SHORT
├── status: ACTIVE | PENDING | COMPLETED
└── grid: PositionGrid
    └── layers[]
        ├── Layer 1 (L1)
        │   ├── R0: 初期エントリー（サイクルヘッド候補）
        │   ├── R1: カウンター 1
        │   ├── R2: カウンター 2
        │   └── ... R(r_max)
        ├── Layer 2 (L2)
        │   ├── R0: レイヤー初期エントリー
        │   ├── R1: カウンター 1
        │   └── ...
        └── Layer 3 (L3) ...
```

### 4.2 サイクルヘッド（動的）

サイクルヘッドは「グリッド内の最も古いポジション」として動的に決定される。具体的には、レイヤーを L1 から順に走査し、最初に見つかった occupied スロットのエントリーがヘッドとなる。

ヘッドのTPがサイクル完了のトリガーとなる。ヘッドのTP = entry_price ± m_pips × pip_size。

### 4.3 スロットの状態遷移

各スロットは以下の状態を取る:

| 状態 | entry | pending_rebuild | ever_closed | 説明 |
| --- | --- | --- | --- | --- |
| 空・未使用 | None | None | false | エントリーを配置可能 |
| 使用中 | Entry | None | - | ライブエントリーが保持されている |
| SL再建待ち | None | StopLossClosedEntry | false | SLでクローズされ再建を待っている。論理的に「存在する」扱い |
| 空・sealed | None | None | true | 再利用不可。次の逆行で新レイヤーが必要 |

#### スロットの判定プロパティ

| プロパティ | 条件 | 用途 |
| --- | --- | --- |
| `is_occupied` | `entry is not None` | ライブエントリーの有無（TP/SL判定） |
| `is_present` | `entry is not None OR pending_rebuild is not None` | 論理的な存在判定（カウンター追加の距離計算、レイヤー進行判定） |
| `is_pending_rebuild` | `pending_rebuild is not None` | SL再建待ちの判定 |
| `is_available` | `entry is None AND not ever_closed AND pending_rebuild is None` | 新規エントリー配置可能か |

#### クローズ時の状態遷移

- **通常TPクローズ**: スロット番号 ≤ `refill_up_to` → 空・未使用（再建玉可能）、それ以外 → sealed
- **ストップロスクローズ**: → SL再建待ち（`pending_rebuild` にスナップショットを保存）
- **リビルド完了**: SL再建待ち → 使用中（`complete_rebuild` で `pending_rebuild` をクリア）
- **レイヤー初期エントリー（R0）のクローズ**: → sealed（レイヤー除去）

### 4.4 サイクルのステータス

| ステータス | 説明 |
| --- | --- |
| ACTIVE | 通常稼働中 |
| PENDING | グリッドにライブエントリーがないがSL再建待ちスロットがある。再建されたら ACTIVE に復帰 |
| COMPLETED | サイクル完了。新サイクルが作成される |

## 5. シーケンス図

### 5.1 順行時（LONG、価格上昇）

```
Price   155.00  155.10  155.20  155.30  155.40  155.50  155.60
        ──────────────────────────────────────────────────────→
        │                                               │
        ├─ OPEN L1/R0 @ 155.01 (ask)                    │
        │  TP=155.51, SL=154.41                         │
        │                                               │
        │  (価格が順行 → カウンター追加なし)              │
        │                                               │
        └───────────────────────────────────────────────┤
                                                        ├─ TP HIT (bid >= 155.51)
                                                        ├─ CLOSE L1/R0 +50 pips
                                                        └─ 新サイクル作成
```

### 5.2 逆行時（LONG、価格下落）

```
Price   155.00  154.70  154.40  154.15  153.95
        ──────────────────────────────────────→
        │       │       │       │       │
        ├─ OPEN L1/R0 @ 155.01           │
        │  TP=155.51                     │
        │       │                        │
        │       ├─ -30 pips: OPEN L1/R1  │
        │       │  units=2000            │
        │       │       │                │
        │       │       ├─ -60 pips: OPEN L1/R2
        │       │       │  units=3000    │
        │       │       │       │        │
        │       │       │       ├─ -85 pips: OPEN L1/R3
        │       │       │       │  units=4000
        │       │       │       │       │
        │       │       │       │       ├─ -105 pips: OPEN L1/R4
        │       │       │       │       │  units=5000
```

R番号はスロットの位置を表し、SLでクローズされたポジションも含めてカウントされる。

### 5.3 逆行→反転時（カウンターTP）

```
Price   155.00  154.70  154.40  154.70  155.00
        ──────────────────────────────────────→
        │       │       │       │       │
        ├─ OPEN R0      │       │       │
        │       ├─ OPEN R1      │       │
        │       │       ├─ OPEN R2      │
        │       │       │       │       │
        │       │       │  (価格反転↑)   │
        │       │       │       │       │
        │       │       │       ├─ CLOSE R2 (counter TP)
        │       │       │       │       │
        │       │       │       │       ├─ CLOSE R1 (counter TP)
        │       │       │       │       │
        │       │       │       │       │  (R0のTPまで上昇すればサイクル完了)
```

### 5.4 ストップロスとリビルド

```
Price   155.00  154.70  154.42  154.41  ...  154.72  155.01
        ──────────────────────────────────────────────────→
        │       │       │       │            │       │
        ├─ OPEN R0 (SL=154.41)  │            │       │
        │       ├─ OPEN R1 (SL=154.42)       │       │
        │       │       │       │            │       │
        │       │       ├─ R1 SL HIT         │       │
        │       │       │  slot → PENDING_REBUILD    │
        │       │       │       │            │       │
        │       │       │       ├─ R0 SL HIT │       │
        │       │       │       │  slot → PENDING_REBUILD
        │       │       │       │            │       │
        │       │       │       │  (新サイクル作成)    │
        │       │       │       │  (旧サイクル→PENDING) │
        │       │       │       │            │       │
        │       │       │       │  (価格反転↑)│       │
        │       │       │       │            │       │
        │       │       │       │            ├─ R1 REBUILD
        │       │       │       │            │  (bid >= R1元entry)
        │       │       │       │            │       │
        │       │       │       │            │       ├─ R0 REBUILD
        │       │       │       │            │       │  (bid >= R0元entry)
        │       │       │       │            │       │
        │       │       │       │            │       │  サイクル→ACTIVE
```

**重要**: SLでクローズされたスロットは `pending_rebuild` 状態になり、論理的に「存在する」扱いとなる。
これにより:
- 次のカウンター追加はSLスロットをスキップし、次のR番号に配置される
- 逆行距離の計測はSLスロットの元のエントリー価格を基準にする
- 不要なレイヤー追加が防止される

### 5.5 二重反転

```
Price   155.00  154.20  154.70  153.90  155.60
        ──────────────────────────────────────→
        │       │       │       │       │
        ├─ OPEN R0      │       │       │
        │       ├─ OPEN R1, R2  │       │
        │       │       │       │       │
        │       │  (反転↑)      │       │
        │       │       │       │       │
        │       │       ├─ CLOSE R2 (TP)│
        │       │       ├─ CLOSE R1 (TP)│
        │       │       │       │       │
        │       │  (再逆行↓)    │       │
        │       │       │       │       │
        │       │       │       ├─ OPEN R1 (refill)
        │       │       │       ├─ R1 SL → PENDING_REBUILD
        │       │       │       ├─ R0 SL → PENDING_REBUILD
        │       │       │       │       │
        │       │       │       │  (サイクル→PENDING)
        │       │       │       │  (新サイクル作成)
        │       │       │       │       │
        │       │       │  (反転↑)      │
        │       │       │       │       │
        │       │       │       ├─ R1 REBUILD
        │       │       │       ├─ R0 REBUILD
        │       │       │       │  (サイクル→ACTIVE)
        │       │       │       │       │
        │       │       │       │       ├─ R1 TP, R0 TP
        │       │       │       │       │  サイクル完了
```

## 6. 逆行側ロジック（カウンターエントリー）

### 6.1 カウンター追加の前提条件

1. サイクルが ACTIVE
2. ヘッドが含み損状態
3. 同一ティック内でカウンターTPクローズが発生していない

### 6.2 スロット配置の判定

現在のレイヤーの `next_available_counter_slot()` を確認:

- 空きスロットあり → 逆行距離が閾値に達していればエントリーを配置
- 空きスロットなし（`needs_new_layer=true`）→ 新レイヤーを作成

`next_available_counter_slot()` は R1 から順に走査し:
- `is_available`（空・未使用）なスロットを返す
- `is_pending_rebuild`（SL再建待ち）なスロットはスキップして次を探す
- `is_empty and ever_closed`（sealed）なスロットに到達したら `None` を返す（新レイヤーが必要）

### 6.3 逆行距離の計測

逆行距離は `present_slots`（occupied + pending_rebuild）を基準に計測する:

- レイヤー内に present なカウンタースロットがある場合: 最も高いR番号の present スロットの元エントリー価格からの距離
- レイヤー内に present なカウンタースロットがない場合: R0（レイヤー初期エントリー）からの距離

SLでクローズされたスロットの元エントリー価格は `pending_rebuild.entry_price` から取得する。

距離は `mid` 価格で計測。

### 6.4 ロットサイズ

$lot = (slot\_index + 1) \times layer\_base\_units$

## 7. ストップロスと再建

### 7.1 ストップロス価格の計算

各エントリーの建玉時に SL 価格が設定される。計算式:

1. $tp\_pips = |close\_price - entry\_price| / pip\_size$
2. $next\_entry\_price = entry\_price \mp next\_interval\_pips \times pip\_size$（LONGなら-、SHORTなら+）
3. $tp\_pips < next\_interval\_pips$ の場合: $SL = next\_entry\_price$
4. $tp\_pips \ge next\_interval\_pips$ の場合: $SL = next\_entry\_price \mp next\_interval\_pips \times pip\_size$

### 7.2 ストップロスクローズ

各ティックで全エントリーの SL をチェックし、ヒットした全エントリーを一括クローズ:

- LONG: $bid \le stop\_loss\_price$
- SHORT: $ask \ge stop\_loss\_price$

クローズ時の処理:

1. `StopLossClosedEntry` スナップショットを作成（元の entry_price, close_price, units, position_id 等を保存）
2. スロットの `close_for_stop_loss(snapshot)` を呼び出し → `pending_rebuild` 状態に遷移
3. `ClosePositionEvent` を発行（`close_reason="stop_loss"`）

スロットが `pending_rebuild` 状態になるため:
- `is_present = True` → カウンター追加の距離計算に含まれる
- `is_available = False` → 新規カウンターエントリーの配置先にならない
- `is_occupied = False` → TP/SL判定の対象にならない
- `needs_new_layer` が不要に `true` にならない

### 7.3 ストップロス再建

各ティックでグリッド内の `pending_rebuild` スロットをチェックし、価格が元のエントリー価格に戻ったスロットを再建:

- LONG: $bid \ge pending\_rebuild.entry\_price$
- SHORT: $ask \le pending\_rebuild.entry\_price$

再建時の処理:

1. 新しい `Entry` を作成（元と同じパラメータ、`is_rebuild=true`）
2. 元のエントリー価格で再建（`entry_price` を上書き）
3. SL を再計算
4. `slot.complete_rebuild(entry)` を呼び出し → `pending_rebuild` をクリアし `entry` を設定
5. `RebuildPositionEvent` を発行（`original_position_id` を含む）

### 7.4 サイクルの PENDING ステータス

SLクローズによりグリッドのライブエントリーが全て空になった場合:

- `grid.has_pending_rebuilds() = True` → PENDING
- `grid.has_pending_rebuilds() = False` → COMPLETED

PENDING サイクルは再建が実行されると ACTIVE に復帰する。

### 7.5 動的ヘッドのTP到達時

元のヘッド（R0）がSLでクローズされ、カウンターエントリーが動的ヘッドに昇格した場合、そのTPが到達しても `pending_rebuild` スロットが残っていればサイクルは COMPLETED にならず PENDING に遷移する。

## 8. 手動テスト

### 8.1 ビジュアルテストの実行

```bash
cd backend
uv run python -m tests.manual.test_snowball_visual
```

特定のシナリオのみ実行:

```bash
uv run python -m tests.manual.test_snowball_visual 3  # SLとリビルド
uv run python -m tests.manual.test_snowball_visual 5  # SLスロットがカウンター追加をブロック
```

### 8.2 シナリオ一覧

| # | シナリオ | 検証内容 |
| --- | --- | --- |
| 1 | 順行（LONG TP） | 初期エントリー → TP → 再エントリー |
| 2 | 逆行（カウンター追加） | R1, R2, R3... が正しい間隔で追加される |
| 3 | SLとリビルド | SLクローズ → pending_rebuild → 価格戻り → リビルド |
| 4 | 二重反転 | カウンター → TP → 再逆行 → SL → リビルド → TP |
| 5 | SLスロットブロック | R1 SL → R1が pending_rebuild → 次のカウンターはR2 |
