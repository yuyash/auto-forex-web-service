# Snowball Strategy — シーケンス図

## 設定前提

```
r_max = 3, f_max = 2, m_pips = 50, n_pips = 30
refill_up_to = 1, m_th = 70%, m1_th = 50%, n_th = 85%
hedging_enabled = true (LONG + SHORT 並行)
```

以下の図はすべて SHORT サイクル側の動きを示す（LONG は対称）。
価格上昇 = SHORT にとって逆行。

---

## 1. 通常パターン — 建玉→カウンター→全決済→再エントリ

```mermaid
sequenceDiagram
    participant P as 価格
    participant G as PositionGrid
    participant E as Engine

    Note over G: サイクル開始
    E->>G: L0/R0 OPEN (initial, 1000u) TP=149.50
    Note over G: [L0/R0●][ ][ ][ ]

    P->>E: 価格 +30pips 逆行
    E->>G: L0/R1 OPEN (counter, 2000u)
    Note over G: [L0/R0●][L0/R1●][ ][ ]

    P->>E: 価格 +30pips 逆行
    E->>G: L0/R2 OPEN (counter, 3000u)
    Note over G: [L0/R0●][L0/R1●][L0/R2●][ ]

    P->>E: 価格反転 → L0/R2 TP到達
    E->>G: L0/R2 CLOSE (counter_tp) ← 後方から
    Note over G: [L0/R0●][L0/R1●][sealed][ ]

    P->>E: 価格反転継続 → L0/R1 TP到達
    E->>G: L0/R1 CLOSE (counter_tp)
    Note over G: [L0/R0●][refill][ ][ ]

    P->>E: 価格反転継続 → head TP到達
    Note over E: has_counter_entries() = false
    E->>G: L0/R0 CLOSE (tp) → サイクル完了
    E->>G: 新サイクル L0/R0 OPEN (initial)
    Note over G: 新サイクル [L0/R0●][ ][ ][ ]
```

---

## 2. 最大レイヤーまで建玉するパターン

```mermaid
sequenceDiagram
    participant P as 価格
    participant G as PositionGrid
    participant E as Engine

    Note over G: サイクル開始
    E->>G: L0/R0 OPEN (initial)
    Note over G: L0:[R0●][ ][ ][ ]

    P->>E: 逆行 → カウンター追加
    E->>G: L0/R1, L0/R2, L0/R3 順次 OPEN
    Note over G: L0:[R0●][R1●][R2●][R3●]

    Note over E: L0 全スロット使用済 → needs_new_layer

    P->>E: さらに逆行
    E->>G: L1/R0 OPEN (layer_initial)
    Note over G: L0:[R0●][R1●][R2●][R3●]<br/>L1:[R0●][ ][ ][ ]

    P->>E: さらに逆行 → L1 カウンター追加
    E->>G: L1/R1, L1/R2, L1/R3 順次 OPEN
    Note over G: L0:[R0●][R1●][R2●][R3●]<br/>L1:[R0●][R1●][R2●][R3●]

    Note over E: L1 全スロット使用済 → needs_new_layer

    P->>E: さらに逆行
    E->>G: L2/R0 OPEN (layer_initial)
    Note over G: L0:[R0●][R1●][R2●][R3●]<br/>L1:[R0●][R1●][R2●][R3●]<br/>L2:[R0●][ ][ ][ ]

    Note over E: layer_count=3 = f_max+1 → これ以上レイヤー追加不可
    Note over E: L2 内のカウンター追加は可能
```

---

## 3. 途中で反転して決済するパターン（後方から順次決済）

```mermaid
sequenceDiagram
    participant P as 価格
    participant G as PositionGrid
    participant E as Engine

    Note over G: L0:[R0●][R1●][R2●]<br/>L1:[R0●][R1●]

    P->>E: 価格反転 → L1/R1 TP到達
    E->>G: L1/R1 CLOSE (counter_tp) ← 最新レイヤーの最大Rから
    Note over G: L0:[R0●][R1●][R2●]<br/>L1:[R0●][ ]

    Note over E: L1 に R0 のみ残存 & R0 TP到達
    E->>G: L1/R0 CLOSE (layer_initial_tp)
    E->>G: L1 レイヤー除去
    Note over G: L0:[R0●][R1●][R2●]

    P->>E: 反転継続 → L0/R2 TP到達
    E->>G: L0/R2 CLOSE (counter_tp)
    Note over G: L0:[R0●][R1●][sealed]

    P->>E: 反転継続 → L0/R1 TP到達
    E->>G: L0/R1 CLOSE (counter_tp)
    Note over G: L0:[R0●][refill][ ]

    P->>E: 反転継続 → head TP到達
    E->>G: L0/R0 CLOSE (tp) → サイクル完了 → 再エントリ
```

---

## 4. 反転→決済→再逆行→再建玉パターン（refill）

```mermaid
sequenceDiagram
    participant P as 価格
    participant G as PositionGrid
    participant E as Engine

    Note over G: L0:[R0●][R1●][R2●][ ]
    Note over E: refill_up_to=1 → R1はrefillable, R2はsealed

    P->>E: 反転 → L0/R2 TP到達
    E->>G: L0/R2 CLOSE (counter_tp, sealed)
    Note over G: L0:[R0●][R1●][sealed][ ]

    P->>E: 反転継続 → L0/R1 TP到達
    E->>G: L0/R1 CLOSE (counter_tp, refillable)
    Note over G: L0:[R0●][空]  [sealed][ ]

    P->>E: 再逆行 → 30pips
    Note over E: next_available_counter_slot() → R1（空きスロット）
    E->>G: L0/R1 OPEN (counter, 再建玉)
    Note over G: L0:[R0●][R1●][sealed][ ]

    P->>E: さらに逆行
    Note over E: next_available_counter_slot() → R2はsealed → None
    Note over E: needs_new_layer = true
    E->>G: L1/R0 OPEN (layer_initial, 新レイヤー)
    Note over G: L0:[R0●][R1●][sealed][ ]<br/>L1:[R0●][ ][ ][ ]

    P->>E: さらに逆行
    E->>G: L1/R1 OPEN (counter)
    Note over G: L0:[R0●][R1●][sealed][ ]<br/>L1:[R0●][R1●][ ][ ]
```

---

## 5. Shrink プロテクション — 層保存ルール付き前方決済

Shrink の決済優先順位:
1. 低い階層から順にクローズ
2. 同階層内では R 番号が小さい方から
3. **例外**: 階層にポジションが1つしかない場合、上位のいずれかの階層に
   複数ポジションがあれば、その上位階層の古いポジションを先にクローズ

```mermaid
sequenceDiagram
    participant P as 価格
    participant G as PositionGrid
    participant E as Engine
    participant M as マージン監視

    Note over G: L0:[R0●][R1●]<br/>L1:[R0●][R1●][R2●][R3●]

    M->>E: margin_ratio=72% ≥ m_th=70%
    Note over E: Shrink 発動

    Note over E: ① L0 に2つ → 最小R = L0/R0
    E->>G: L0/R0 CLOSE (shrink)
    Note over G: L0:[sealed][R1●]<br/>L1:[R0●][R1●][R2●][R3●]
    Note over E: head → L0/R1 に自動移動

    Note over E: ② L0 に1つ、L1 に4つ(≥2) → L0スキップ → L1/R0
    E->>G: L1/R0 CLOSE (shrink)
    Note over G: L0:[sealed][R1●]<br/>L1:[sealed][R1●][R2●][R3●]

    Note over E: ③ L0 に1つ、L1 に3つ(≥2) → L0スキップ → L1/R1
    E->>G: L1/R1 CLOSE (shrink)
    Note over G: L0:[sealed][R1●]<br/>L1:[sealed][sealed][R2●][R3●]

    Note over E: ④ L0 に1つ、L1 に2つ(≥2) → L0スキップ → L1/R2
    E->>G: L1/R2 CLOSE (shrink)
    Note over G: L0:[sealed][R1●]<br/>L1:[sealed][sealed][sealed][R3●]

    Note over E: ⑤ L0 に1つ、L1 に1つ → 上位にmultiなし → L0/R1
    E->>G: L0/R1 CLOSE (shrink)
    Note over G: L0:[sealed][sealed]<br/>L1:[sealed][sealed][sealed][R3●]
    Note over E: head → L1/R3 に自動移動

    M->>E: ratio < m1_th
    Note over E: Shrink 完了 → NORMAL復帰

    Note over E: 以降 L1/R3 が cycle head<br/>L1/R3 の TP 到達でサイクル完了
```

### 層保存ルールの判定フロー

```mermaid
flowchart TD
    A[最低層から走査] --> B{この層に<br/>ポジション数は?}
    B -->|0| C[次の層へ]
    B -->|2以上| D[最小Rをクローズ]
    B -->|1| E{上位のいずれかの層に<br/>2以上のポジションがある?}
    E -->|Yes| F[この層をスキップ<br/>上位層を走査]
    E -->|No| G[この1つをクローズ]
```
```

---

## 6. Lock プロテクション — 両建てヘッジ

```mermaid
sequenceDiagram
    participant P as 価格
    participant G as PositionGrid
    participant E as Engine
    participant M as マージン監視

    Note over G: LONG: L0:[R0●][R1●]<br/>SHORT: L0:[R0●][R1●][R2●]

    M->>E: margin_ratio=87% ≥ n_th=85%
    Note over E: Lock 発動

    E->>E: net = long_units - short_units
    Note over E: net < 0 → LONG ヘッジ追加
    E->>G: hedge OPEN (LONG, |net| units)
    Note over E: 全取引停止（Lock中）

    loop Lock 中の各 tick
        P->>E: tick受信
        M->>E: ratio チェック
        Note over E: ratio ≥ m_th-5 → Lock 継続
    end

    M->>E: ratio=63% < m_th-5=65%
    Note over E: Lock 解除
    E->>G: hedge CLOSE (lock_hedge_neutralize)
    Note over E: 通常取引再開
```

---

## 7. Emergency Stop

```mermaid
sequenceDiagram
    participant P as 価格
    participant E as Engine
    participant M as マージン監視

    M->>E: margin_ratio=96% ≥ 95%
    Note over E: 🚨 Emergency Stop
    E-->>E: should_stop=true
    Note over E: タスク FAILED 終了<br/>全ポジション手動対応が必要
```

---

## 8. on_tick 全体フロー

```mermaid
flowchart TD
    A[tick 受信] --> B[NAV 更新]
    B --> C[margin_ratio 算出]
    C --> D{ratio ≥ 95%?}
    D -->|Yes| E[🚨 Emergency Stop]
    D -->|No| F{ratio ≥ n_th?}
    F -->|Yes| G[Lock 発動: ヘッジ追加]
    F -->|No| H{Lock 中?}
    H -->|Yes| I{ratio < m_th-5?}
    I -->|Yes| J[Lock 解除: ヘッジ決済]
    I -->|No| K[何もしない]
    H -->|No| L{ratio ≥ m_th?}
    L -->|Yes| M[Shrink: 前方から決済]
    L -->|No| N{初期化済?}
    N -->|No| O[LONG + SHORT サイクル作成]
    N -->|Yes| P[各サイクル処理]

    P --> Q{head TP 到達?}
    Q -->|Yes & カウンターなし| R[head 決済 → 再エントリ]
    Q -->|Yes & カウンターあり| S[❌ Close Order Violation]
    Q -->|No| T{カウンター TP 到達?}
    T -->|Yes| U[後方から決済]
    T -->|No| V{逆行閾値超過?}
    V -->|Yes & スロット空き| W[カウンター追加]
    V -->|Yes & スロット満杯| X{f_max 未到達?}
    X -->|Yes| Y[新レイヤー追加]
    X -->|No| Z[何もしない]
    V -->|No| Z
```

---

## PositionGrid 構造

```
サイクル (SHORT, r_max=3, f_max=2)

L0: [R0:initial] [R1:counter] [R2:counter] [R3:counter]
L1: [R0:layer_initial] [R1:counter] [R2:counter] [R3:counter]
L2: [R0:layer_initial] [R1:counter] [R2:counter] [R3:counter]

通常TP決済:  ←←←←←←←←←←←← 後方(newest)から前方(oldest)へ
Shrink決済:  →→→→→→→→→→→→ 前方(oldest)から後方(newest)へ

head_entry() = グリッド内の最古の生存ポジション（動的）
  L0/R0 が決済されたら → L0/R1 が自動的に head に
  L0 が空になったら → L1/R0 が head に
```
