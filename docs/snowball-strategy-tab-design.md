# Snowball Strategy Tab Design

## Goal

バックテスト詳細ページとトレーディングタスク詳細ページに `Strategy` タブを追加し、Snowball Strategy の挙動を「多数のポジション一覧」ではなく「各 Initial Entry を起点とした実行単位」で追跡できるようにする。

対象ユーザーの主な確認ポイント:

- 順行側が `m_pips` どおりに利益確定しているか
- 逆行側が Strategy Configuration の pips 間隔どおりに増し玉しているか
- 逆行側の利確価格が設定モードどおりに計算・実行されているか
- 防御ロジックがいつ発動し、何を止めたか

## Current State

既存実装で利用できるデータ:

- `StrategyEventRecord.details`
  - `entry_id`
  - `layer_number`
  - `retracement_count`
  - `planned_exit_price`
  - `planned_exit_price_formula`
  - `direction`
  - `price` / `entry_price` / `exit_price`
- `Position`
  - `planned_exit_price`
  - `planned_exit_price_formula`
  - `layer_index`
  - `retracement_count`
- `Trade`
  - `execution_method`
  - `layer_index`
  - `retracement_count`
- 詳細画面の既存タブ構成
  - [frontend/src/components/backtest/BacktestTaskDetail.tsx](/home/yuyash/Workplace/AutoForex/frontend/src/components/backtest/BacktestTaskDetail.tsx)
  - [frontend/src/components/trading/TradingTaskDetail.tsx](/home/yuyash/Workplace/AutoForex/frontend/src/components/trading/TradingTaskDetail.tsx)

既存データだけでは不足する点:

- counter add が「どの trend 側 Initial Entry から派生したものか」を厳密に復元できない
- trend / counter / hedge / rebalance / shrink などの文脈がイベントから安定して引けない
- 「期待された interval / tp」と「実際の発火価格差」を比較する計算結果が永続化されていない

## Design Summary

`Strategy` タブは単なるイベント一覧ではなく、Snowball 実行を次の 2 層で見せる。

1. Execution Runs List
   - `Initial Entry` を起点とする run カード一覧
   - 1 run = 1 つの trend-side 起点と、それに紐づく counter-side add/close の流れ
2. Run Detail
   - タイムライン
   - 価格ステップ検証
   - 利確検証
   - 防御イベント

UI 上は `Overview` の右に `Strategy` を追加する。

Snowball 固有の表現は持ちつつも、将来 Floor や他戦略を追加できるよう、API のトップレベル骨格は共通化する。

## Backend Design

### 1. Extend Existing `strategy-events`

新しい endpoint は追加せず、既存の `strategy-events` の契約を Snowball 可視化向けに変更する。

- Backtest: `GET /api/trading/tasks/backtest/{id}/strategy-events/`
- Trading: `GET /api/trading/tasks/trading/{id}/strategy-events/`

クエリ案:

- `execution_id`
- `root_entry_id`
- `page`
- `page_size`

振る舞い:

- `strategy-events` は今後「strategy の内部生イベント一覧」ではなく、「strategy 可視化用の集約 read model」を返す endpoint とする
- strategy 固有の集約ロジックは、task の実際の `strategy_type` をサーバー側で判定して適用する

共通レスポンス骨格:

```json
{
  "strategy_type": "snowball",
  "supported": true,
  "execution_id": "uuid",
  "generated_at": "2026-03-19T00:00:00Z",
  "summary": {},
  "view_model": {
    "kind": "snowball_runs",
    "groups": []
  }
}
```

設計原則:

- トップレベル envelope は全戦略で共通にする
- strategy 固有差分は `view_model.kind` と `view_model.groups` 配下に閉じ込める
- `summary` は共通の最小キーを持ち、strategy 固有キーを追加可能にする

`summary` の共通キー候補:

- `group_count`
- `active_group_count`
- `completed_group_count`
- `intervened_group_count`
- `open_position_count`
- `closed_position_count`

Snowball のレスポンス案:

```json
{
  "strategy_type": "snowball",
  "supported": true,
  "execution_id": "uuid",
  "generated_at": "2026-03-19T00:00:00Z",
  "summary": {
    "group_count": 24,
    "active_group_count": 3,
    "completed_group_count": 20,
    "intervened_group_count": 1,
    "open_position_count": 8,
    "closed_position_count": 57,
    "counter_add_count": 63,
    "counter_close_count": 41,
    "protection_event_count": 3
  },
  "view_model": {
    "kind": "snowball_runs",
    "groups": [
      {
        "group_id": "101",
        "root_entry_id": 101,
        "started_at": "2026-03-19T00:00:00Z",
        "ended_at": "2026-03-19T02:15:00Z",
        "status": "active",
        "root_direction": "long",
        "root_basket": "trend",
        "trigger_side": "long",
        "config_snapshot": {
          "m_pips": "50",
          "interval_mode": "constant",
          "counter_tp_mode": "weighted_avg"
        },
        "checks": {
          "trend_tp": { "passed": true, "expected_pips": "50", "actual_pips": "50.1" },
          "counter_intervals": { "passed_count": 3, "failed_count": 0 },
          "counter_tp": { "passed_count": 2, "failed_count": 0 }
        },
        "steps": [
          {
            "kind": "initial_entry",
            "entry_id": 101,
            "timestamp": "2026-03-19T00:00:00Z",
            "basket": "trend",
            "direction": "long",
            "price": "150.000",
            "units": 1000,
            "expected_exit_price": "150.500",
            "expected_exit_formula": "150.000 + 50 * 0.01"
          },
          {
            "kind": "counter_add",
            "entry_id": 120,
            "parent_entry_id": 101,
            "step": 1,
            "timestamp": "2026-03-19T00:30:00Z",
            "direction": "short",
            "price": "149.700",
            "expected_interval_pips": "30",
            "actual_interval_pips": "30.0",
            "within_tolerance": true
          }
        ],
        "protection_events": [
          {
            "kind": "shrink",
            "timestamp": "2026-03-19T01:40:00Z",
            "details": {}
          }
        ]
      }
    ]
  }
}
```

Floor を将来追加する場合のイメージ:

```json
{
  "strategy_type": "floor",
  "supported": true,
  "execution_id": "uuid",
  "generated_at": "2026-03-19T00:00:00Z",
  "summary": {
    "group_count": 12,
    "active_group_count": 2,
    "completed_group_count": 10,
    "open_position_count": 5,
    "closed_position_count": 31
  },
  "view_model": {
    "kind": "floor_layers",
    "groups": [
      {
        "group_id": "layer-1",
        "layer_index": 1,
        "status": "active",
        "steps": []
      }
    ]
  }
}
```

### 2. Aggregation Service

新規サービス:

- `backend/apps/trading/services/strategy_visualization.py`

責務:

- task / execution を基点に StrategyEventRecord, Position, Trade を収集
- strategy_type ごとに適切な group 単位へ再構成
- 「期待値 vs 実績」を計算
- 共通 envelope を持つ UI 向け DTO を返却

### 3. Persistence Model Changes

Snowball の実行単位を安定して追跡するため、`StrategyEventRecord` に新しい永続フィールドを追加する。

対象:

- [backend/apps/trading/models/events.py](/home/yuyash/Workplace/AutoForex/backend/apps/trading/models/events.py)

追加候補フィールド:

- `strategy_type`
  - `CharField`
  - task の strategy type を event record に複写
- `visual_group_id`
  - `CharField`
  - Strategy タブ上の group 識別子
  - Snowball では `root_entry_id` を文字列化した値を格納
- `root_entry_id`
  - `BigIntegerField(null=True)`
  - 一連の実行を束ねる起点 entry
- `parent_entry_id`
  - `BigIntegerField(null=True)`
  - 直接の親 entry
- `entry_id`
  - `BigIntegerField(null=True)`
  - event 自身が対象とする entry
- `basket`
  - `CharField`
  - `trend` / `counter` / `hedge` / `layer` など
- `step`
  - `IntegerField(null=True)`
  - strategy 内 step 番号
- `close_reason`
  - `CharField`
  - `trend_tp` / `counter_tp` / `shrink` / `rebalance` / `lock_hedge_neutralize`
- `position_id`
  - `UUIDField(null=True)`
  - close/open 対象 position
- `direction`
  - `CharField`
  - 可視化用に正規化した long/short
- `event_timestamp`
  - `DateTimeField(null=True, db_index=True)`
  - strategy event の論理発生時刻

検証系の永続フィールド候補:

- `expected_interval_pips`
  - `DecimalField(null=True, max_digits=12, decimal_places=4)`
- `actual_interval_pips`
  - `DecimalField(null=True, max_digits=12, decimal_places=4)`
- `expected_tp_pips`
  - `DecimalField(null=True, max_digits=12, decimal_places=4)`
- `actual_tp_pips`
  - `DecimalField(null=True, max_digits=12, decimal_places=4)`
- `expected_exit_price`
  - `DecimalField(null=True, max_digits=20, decimal_places=10)`
- `actual_exit_price`
  - `DecimalField(null=True, max_digits=20, decimal_places=10)`
- `validation_tolerance_pips`
  - `DecimalField(null=True, max_digits=12, decimal_places=4)`
- `validation_status`
  - `CharField`
  - `pass` / `warn` / `fail` / `not_applicable`

方針:

- group 識別と検索で使う値は JSON ではなく列にする
- 表示補助や strategy 固有の追加文脈は引き続き `details` に残してよい
- `details` は補助、列は正規化された検索・集約キーという役割分担にする

推奨インデックス:

- `(task_type, task_id, execution_id, strategy_type, event_timestamp desc)`
- `(task_type, task_id, execution_id, visual_group_id, event_timestamp)`
- `(task_type, task_id, execution_id, root_entry_id, event_timestamp)`
- `(task_type, task_id, execution_id, basket, event_timestamp)`

### 4. Strategy Event Base Model Changes

`StrategyEvent` 系 dataclass 自体にも、永続化される識別・検証メタデータを持たせる。

対象:

- [backend/apps/trading/events/base.py](/home/yuyash/Workplace/AutoForex/backend/apps/trading/events/base.py)

追加候補:

- `strategy_type`
- `visual_group_id`
- `root_entry_id`
- `parent_entry_id`
- `basket`
- `step`
- `close_reason`
- `validation_status`
- `expected_interval_pips`
- `actual_interval_pips`
- `expected_tp_pips`
- `actual_tp_pips`
- `expected_exit_price`
- `actual_exit_price`
- `validation_tolerance_pips`

方針:

- `to_dict()` だけに頼らず、model factory が安全に読める属性として event object に載せる
- `StrategyEventRecord.from_event()` で属性から列へ正規化して保存する
- 同じ値を `details` にも残して、デバッグと OpenAPI 上の説明をしやすくする

### 5. Required Event Enrichment

正しい grouping のため、Snowball が出す event metadata を追加する。

対象:

- [backend/apps/trading/strategies/snowball/strategy.py](/home/yuyash/Workplace/AutoForex/backend/apps/trading/strategies/snowball/strategy.py)
- [backend/apps/trading/events/base.py](/home/yuyash/Workplace/AutoForex/backend/apps/trading/events/base.py)

追加したい event metadata:

- `basket`: `trend` / `counter` / `hedge`
- `visual_group_id`
- `root_entry_id`: その run の起点 Initial Entry
- `parent_entry_id`: 直接のトリガー元 entry
- `entry_id`
- `step`: Snowball の step 番号
- `close_reason`: `trend_tp` / `counter_tp` / `shrink` / `rebalance` / `lock_hedge_neutralize`
- `expected_interval_pips`
- `actual_interval_pips`
- `expected_tp_pips`
- `actual_tp_pips`
- `expected_exit_price`
- `actual_exit_price`
- `validation_tolerance_pips`
- `protection_level`

重要:

`root_entry_id` を strategy 側で明示的に持たせる。これを入れないと UI 側や集約 API 側で推測ロジックが必要になり、Snowball の検証画面として信頼性が落ちる。

重要:

Snowball 側では event 発生時に `root_entry_id` と `visual_group_id` を決定し、その場で event object に付与する。集約 API 側で推測しない。

### 6. Event Save Pipeline Changes

保存パイプラインでも新しい列へマッピングする変更が必要。

対象:

- [backend/apps/trading/tasks/executor.py](/home/yuyash/Workplace/AutoForex/backend/apps/trading/tasks/executor.py)

必要な変更:

- `StrategyEventRecord.from_event()` を拡張し、新しい列を event 属性から埋める
- `TradingEvent.from_event()` にも必要なら `strategy_type` や `entry_id` を複写する
- `save_events()` の bulk create 前提を維持しつつ、新しい列が null-safe に保存されるようにする
- strategy event と execution event の両方で共有される識別子は、変換時に落とさない

### 7. Serializer / View

追加候補:

- serializer: `StrategyVisualizationSerializer`
- `strategy_events` action のレスポンス契約変更

実装場所の第一候補:

- [backend/apps/trading/views/mixins.py](/home/yuyash/Workplace/AutoForex/backend/apps/trading/views/mixins.py)

### 8. API Behavior for Non-Snowball Strategies

- strategy 固有集約が未実装の場合は 200 で以下を返す
  - `supported: false`
  - `strategy_type: <task strategy type>`
  - `summary: {}`
  - `view_model: { "kind": "unsupported", "groups": [] }`
  - `message: "Strategy visualization is not implemented for this strategy yet."`

これにより、タブ自体は将来他戦略へ拡張しやすい。

### 9. Breaking Change Policy

この変更は意図的に breaking change とする。

- `strategy-events` の既存レスポンス互換は維持しない
- 既存レスポンスを利用している箇所はすべて新契約に合わせて修正する
- OpenAPI / 型定義 / テストも新契約に合わせて更新する

現時点で影響が見えている箇所:

- [frontend/src/hooks/useTaskEvents.ts](/home/yuyash/Workplace/AutoForex/frontend/src/hooks/useTaskEvents.ts)
- [frontend/src/components/tasks/detail/TaskEventsTable.tsx](/home/yuyash/Workplace/AutoForex/frontend/src/components/tasks/detail/TaskEventsTable.tsx)
- [frontend/src/components/backtest/BacktestTaskDetail.tsx](/home/yuyash/Workplace/AutoForex/frontend/src/components/backtest/BacktestTaskDetail.tsx)
- [frontend/src/components/trading/TradingTaskDetail.tsx](/home/yuyash/Workplace/AutoForex/frontend/src/components/trading/TradingTaskDetail.tsx)
- [frontend/src/hooks/useWindowedTaskMarkers.ts](/home/yuyash/Workplace/AutoForex/frontend/src/hooks/useWindowedTaskMarkers.ts)

対応方針:

- `TaskEventsTable` の strategy source 利用を廃止または別 UI に置き換える
- 一般イベント一覧は既存の `events` endpoint に寄せる
- `strategy-events` は Strategy タブ専用データソースとして再定義する

### 10. Migration Strategy

後方互換性は不要なので、データ移行は最小限でよい。

方針:

- schema migration で新しい列を追加する
- 既存行の backfill は必須にしない
- 新しい Strategy タブは、新列が入っている execution のみを正しく可視化対象とみなす
- 古い execution に対しては
  - `supported: false`
  - `message: "Strategy visualization is unavailable for executions recorded before the visualization schema update."`
  を返してよい

必要なら後続フェーズで best-effort backfill を別管理コマンドで実装する。

## Frontend Design

### 1. Tab Placement

両画面で `Strategy` タブを `Overview` の右に追加する。

- [frontend/src/components/backtest/BacktestTaskDetail.tsx](/home/yuyash/Workplace/AutoForex/frontend/src/components/backtest/BacktestTaskDetail.tsx)
- [frontend/src/components/trading/TradingTaskDetail.tsx](/home/yuyash/Workplace/AutoForex/frontend/src/components/trading/TradingTaskDetail.tsx)

default tab order:

1. `overview`
2. `strategy`
3. `trend`
4. `positions`
5. `trades`
6. `orders`
7. `events`
8. `logs`

### 2. New Components

候補構成:

- `frontend/src/components/tasks/detail/strategy/TaskStrategyTab.tsx`
- `frontend/src/components/tasks/detail/strategy/StrategyRunList.tsx`
- `frontend/src/components/tasks/detail/strategy/StrategyRunTimeline.tsx`
- `frontend/src/components/tasks/detail/strategy/StrategyRunChecks.tsx`
- `frontend/src/components/tasks/detail/strategy/StrategyProtectionEvents.tsx`
- `frontend/src/components/tasks/detail/strategy/StrategyViewModelRenderer.tsx`

### 3. New Hook / API Client

- `frontend/src/hooks/useTaskStrategyEvents.ts`

既存の `strategy-events` endpoint をそのまま呼ぶ。`useTaskEvents` の `source='strategy'` とは責務が変わるため、可視化専用 hook に切り出す。

### 4. Frontend Type Design

レスポンス型は共通 envelope と strategy 別 view model の discriminated union にする。

例:

- `StrategyVisualizationResponse`
  - `strategy_type`
  - `supported`
  - `execution_id`
  - `generated_at`
  - `summary`
  - `view_model`
- `SnowballRunsViewModel`
  - `kind: 'snowball_runs'`
  - `groups: SnowballRunGroup[]`
- `FloorLayersViewModel`
  - `kind: 'floor_layers'`
  - `groups: FloorLayerGroup[]`
- `UnsupportedStrategyViewModel`
  - `kind: 'unsupported'`
  - `groups: []`

### 5. Main Screen Layout

上段:

- run summary chips
- filter
  - direction
  - run status
  - validation result only

左カラム:

- run list
  - `Initial Entry #101`
  - direction
  - status
  - started_at / ended_at
  - validation badge

右カラム:

- timeline
- check panels
- related positions / trades quick links

共通 UI 方針:

- 画面コンテナは `summary` と `view_model` を読む共通コンポーネントにする
- `view_model.kind` に応じて strategy 別 renderer を切り替える
  - `snowball_runs` -> Snowball renderer
  - `floor_layers` -> Floor renderer
  - `unsupported` -> fallback message

### 6. Timeline Semantics

タイムラインのイベント種別:

- `Initial Entry`
- `Trend TP`
- `Trend Re-entry`
- `Counter Add #n`
- `Counter TP #n`
- `Shrink Close`
- `Rebalance Close`
- `Lock`
- `Unlock`
- `Emergency Stop`

各イベントで表示する主情報:

- 実行時刻
- price
- pips difference
- expected formula / expected target
- actual result
- pass / warn / fail

### 7. Validation Rules in UI

UI 側は原則「計算し直す」のではなく、バックエンドが返した検証値を表示する。

理由:

- 戦略仕様の単一責任をバックエンドに寄せたい
- Trading / Backtest で同じ判定を使いたい
- 将来 Snowball パラメータが増えたときに UI の再実装を避けたい

## Reconstruction Rules

run 再構成ルール:

1. `basket=trend` かつ `kind=initial_entry or trend_reentry` の open event を run の起点候補とする
2. 各 event は `root_entry_id` によって 1 run に所属する
3. counter add / counter close / protection close は同じ `root_entry_id` にぶら下げる
4. run は root position が close 済みかつ未処理の protection event がなければ `completed`
5. root position が開いたままなら `active`

このルールは `root_entry_id` 導入が前提。

補足:

- API 集約時は `visual_group_id` を第一キーに使う
- Snowball では `visual_group_id == str(root_entry_id)` としてよい
- 将来 Floor では `visual_group_id == "layer-{layer_index}"` のような strategy 固有規約にする

## Performance Considerations

- 一覧表示は run 単位ページネーション
- 各 run に含める step は最初から全部返してよい
  - Snowball は 1 run あたりの step 数が限定的
- detail polling は `RUNNING` / `STARTING` のときのみ
- 増分 polling は既存 `since` ベースの単純 merge を使わず、まずフル再取得を基本にする
  - 理由: run 集約結果は単純 merge では整合性が崩れやすい

## Test Plan

### Backend

- service unit tests
  - trend TP が `m_pips` と一致
  - counter add interval が config と一致
  - weighted average TP の検証
  - fixed/additive/subtractive/multiplicative/divisive TP の検証
  - shrink / rebalance / lock イベントの grouping
  - `StrategyEventRecord` 新列への永続化
  - `visual_group_id` / `root_entry_id` / `parent_entry_id` の保存
- API tests
  - backtest `strategy-events`
  - trading `strategy-events`
  - unsupported strategy response
  - pre-schema-update execution fallback

### Frontend

- hook tests
  - loading / error / success
  - polling merge
- component tests
  - run list rendering
  - detail timeline rendering
  - unsupported strategy state

## Implementation Phases

### Phase 1

- `StrategyEventRecord` 新列追加 migration
- `StrategyEvent` base metadata 拡張
- Snowball strategy で `visual_group_id` / `root_entry_id` / `parent_entry_id` を付与
- `Strategy` タブ追加
- `strategy-events` 契約変更
- run list + timeline の最小表示

### Phase 2

- 検証系フィールドの永続化
- Strategy aggregation service 実装
- expected vs actual validation panel
- protection events panel
- filter / badges / quick links

### Phase 3

- old execution fallback / optional backfill command
- chart overlay 連携
- trend tab との deep link
- CSV export

## Open Questions

1. `Initial Entry` の定義を「初回両建てのみ」にするか、「trend re-entry も新 run」とみなすか
2. `weighted_avg` モードでは「平均価格そのもの」を pass 条件にするか、「close trigger 到達時の price 差」を pass 条件にするか
3. protection 系 close を run の失敗とみなすか、単なる別種イベントとみなすか

現時点の提案:

1. trend re-entry も新 run とみなす
2. `expected_exit_price` と実際 close price の差で判定する
3. protection 系は fail ではなく `intervened` ステータスで分離する

## Proposed Files

バックエンド:

- `backend/apps/trading/services/strategy_visualization.py`
- `backend/apps/trading/serializers/strategy_visualization.py`
- `backend/apps/trading/migrations/<new_migration>.py`
- `backend/apps/trading/views/mixins.py`
- `backend/apps/trading/models/events.py`
- `backend/apps/trading/events/base.py`
- `backend/apps/trading/strategies/snowball/strategy.py`
- `backend/apps/trading/tasks/executor.py`
- `backend/tests/unit/trading/services/test_strategy_visualization.py`
- `backend/tests/unit/trading/models/test_strategy_event_record.py`
- `backend/tests/unit/trading/strategies/snowball/test_strategy_visualization_metadata.py`
- `backend/tests/api/trading/test_strategy_visualization.py`

フロントエンド:

- `frontend/src/components/tasks/detail/strategy/TaskStrategyTab.tsx`
- `frontend/src/components/tasks/detail/strategy/StrategyRunList.tsx`
- `frontend/src/components/tasks/detail/strategy/StrategyRunTimeline.tsx`
- `frontend/src/components/tasks/detail/strategy/StrategyRunChecks.tsx`
- `frontend/src/components/tasks/detail/strategy/StrategyProtectionEvents.tsx`
- `frontend/src/components/tasks/detail/strategy/StrategyViewModelRenderer.tsx`
- `frontend/src/hooks/useTaskStrategyEvents.ts`
- `frontend/src/types/strategyVisualization.ts`
- `frontend/src/components/tasks/detail/strategy/StrategyRunChecks.tsx`
- `frontend/src/hooks/useTaskStrategyEvents.ts`
- `frontend/src/types/strategyVisualization.ts`
