# KYOUKAI 終幕実装記録

作成日: 2026-07-11

## 進捗表

```text
KYOUKAI終幕制作進捗

[x] 1. 最終ルートの名前・到達条件・終了条件
[ ] 2. 最終電話の会話・発信者・着信仕様
[ ] 3. 最上階・鍵穴イベント仕様
[ ] 4. 消滅の鍵の正式仕様
[ ] 5. 逆観測室の終幕演出・最終文
[ ] 6. 管理日誌の終幕ページ
[ ] 7. 状態フラグ・localStorage・再訪設計
[ ] 8. 終幕用画像・音・UI素材仕様
[ ] 9. 統合実装・テスト
[ ] 10. 終了告知・Shorts・SNS文面
```

## 制作物04

受領日: 2026-07-13
仕様名: 消滅の鍵の正式仕様
状態: 実装・検証完了
変更ファイル:
- `data/scenarios/route_e.json`
- `static/kyoukai-scenario-events.js`
- `static/kyoukai-scenario.js`
- `templates/kanrinin.html`
- `static/kanrinin.js`
- `static/kanrinin.css`
- `templates/top-floor.html`
- `static/top-floor.js`
- `static/space.css`
- `main.py`
- `tests/test_route_e_scenario.py`

実装内容:
- `annihilation_key` をRoute_E専用の正式な鍵として扱い、管理人室の鍵ボックスからのみ取得できるようにした。
- 取得条件をシナリオモード、Route_E active、最終電話完了、終幕未完了、未取得に限定し、フリーモードでは取得処理を発生させない。
- 取得時に `annihilation_key_obtained`, `annihilation_key_obtained_at`, `annihilation_key_used`, `annihilation_key_consumed`, `key_box_state`, `route_e_stage` を更新し、鍵ボックス再確認時は空表示のみ返すようにした。
- 最上階の鍵穴で、鍵所持時のみ「鍵穴の奥で、何かが待っている。」「消滅の鍵を差し込みます。」を表示し、次クリック/タップで差し込み・回転演出を開始するようにした。
- 使用完了時に `annihilation_key_used`, `annihilation_key_used_at`, `annihilation_key_consumed`, `top_floor_keyhole_completed`, `top_floor_event_completed`, `keyhole_state`, `route_e_stage`, `current_target_room_id` を更新し、次工程の観測者遷移待ちへ進める状態にした。
- Route_Eの鍵使用では通常404へ遷移せず、既存の `/kanrinin/deleted` 404導線はRoute_E外の旧動作として残した。
- 使用中リロード時に未完了なら `keyhole_state` を `ready` へ戻し、鍵所持を維持する回復処理を追加した。

未実装として残す内容:
- 観測者の最終演出・最終文章
- 管理人日記の最終更新
- Route_E全体の完了処理・`ending_completed`
- 終幕後の再訪問仕様

確認内容:
- `tests/test_route_e_scenario.py` に制作物04の取得条件、状態保存、鍵ボックス空表示、鍵穴使用、404非遷移、回復処理のテストを追加した。

## 制作物05

受領日: 2026-07-13
仕様名: 逆観測室の終幕演出・最終文
状態: 実装・検証完了
変更ファイル:
- `data/scenarios/route_e.json`
- `static/kyoukai-scenario-events.js`
- `static/kyoukai-scenario.js`
- `templates/top-floor.html`
- `static/top-floor.js`
- `static/space.css`
- `templates/observer.html`
- `static/observer.js`
- `static/observer.css`
- `main.py`
- `tests/test_route_a_scenario.py`
- `tests/test_route_e_scenario.py`

実装内容:
- 消滅の鍵使用後、最上階の完了文を表示したあと短い暗転で `/observer` に遷移するようにした。
- `/observer` は通常状態を維持しつつ、Route_E条件を満たす場合だけ `route_e_final` 表示へ切り替えるようにした。
- 終幕専用の12テキストを一文ずつ表示し、クリック/タップまたはEnter/Spaceで進行する。自動送り、選択肢、発言者名は出さない。
- 最終文後にだけ「管理人室へ戻る」ボタンを表示し、押下時に `observer_final_event_completed`, `observer_reversed`, `user_selected_manager_return`, `route_e_stage = "manager_return"` を保存して管理人室へ戻すようにした。
- 実カメラ、マイク、個人情報、ホラーUI、スタッフロール、SNS導線は追加していない。
- Route_E全体の完了、`ending_completed`, `kyoukai_completed_at`, 管理人日記終幕ページ解放は制作物06以降に残した。

確認内容:
- `tests/test_route_e_scenario.py` に制作物05の遷移条件、終幕テキスト、帰還ボタン、状態保存、Route_E未完了維持のテストを追加した。

## 制作物02

受領日: 2026-07-11
仕様名: 最終電話の会話・発信者・着信仕様
状態: 完了

変更ファイル:
- `data/scenarios/route_e.json`
- `static/kyoukai-scenario-events.js`
- `static/kyoukai-scenario.js`
- `static/kanrinin.js`
- `static/kanrinin.css`
- `templates/kanrinin.html`
- `main.py`
- `tests/test_route_e_scenario.py`
- `tests/test_route_a_scenario.py`

実装内容:
- 最終電話の発信者を `route_e_caller_001`、表示名を `記録なし`、種別を `unknown_record` として登録した。
- Route_AからRoute_Dの個別完了、シナリオモード、管理人室、Route_E待機状態、終幕未完了、最終電話未完了を着信条件にした。
- 通常電話より高い priority を設定し、Route_E最終電話を優先するようにした。
- 初回は管理人室再入室後20秒、通話途中離脱後はRoute_E activeのまま1.5秒で再着信する条件を追加した。
- 電話を取った時点で `route_e` を active、`active_route_id` を `route_e` にし、`route_e_started_at` と受話時刻を保存するようにした。
- 会話本文10件をデータ側に登録し、改行指定を保持した。
- 最終電話だけ手動進行にし、発信者名 `記録なし` を上部、本文を下部に表示するようにした。
- 通話完了時に `route_e_phone_completed` と完了時刻を保存し、`top_floor_unlocked` を true、`route_e_stage` を `route_e_top_floor_unlocked` に更新するようにした。
- 通話完了後は `最上階が開放されました。` を短時間だけ表示するようにした。
- 通話途中の退出・リロードでは電話UI状態を idle に戻し、Route_E active、最上階未開放、電話未完了を維持して再入室時に冒頭から再着信するようにした。

未実装として残す内容:
- 最上階内部イベント、鍵穴、消滅の鍵、逆観測室、管理人日記終幕ページ、Route_E完了処理、終幕後の再訪仕様、新規音源、SNS告知は制作物03以降で扱う。

確認内容:
- Route_E最終電話の発信者、本文、手動進行、20秒待機、1.5秒復帰、完了状態、最上階開放フラグをテスト対象に追加した。

## 制作物03

受領日: 2026-07-13
仕様名: 最上階・鍵穴イベント仕様
状態: 完了

変更ファイル:
- `data/scenarios/route_e.json`
- `static/kyoukai-scenario-events.js`
- `static/kyoukai-scenario.js`
- `templates/top-floor.html`
- `static/top-floor.js`
- `static/space.css`
- `main.py`
- `tests/test_route_e_scenario.py`
- `tests/test_route_a_scenario.py`

実装内容:
- 最上階の表示名をページ上では `最上階`、エレベーター/フロア表示では既存通り `KEY` として維持した。
- `top_floor_entered`, `top_floor_entered_at`, `top_floor_event_completed`, `top_floor_keyhole_completed`, `keyhole_state`, `keyhole_touched`, `keyhole_touched_without_key`, `keyhole_interaction_lock` の保存土台を追加した。
- `keyhole_state` が未完了の `processing` で復帰した場合、鍵所持状態に応じて `ready` または `waiting_for_key` へ戻す補正を追加した。
- Route_E active、最終電話完了、`top_floor_unlocked === true`、終幕未完了の時だけ最上階の鍵穴が操作できるようにした。
- 最上階初回入室時に `route_e_top_floor_enter_001` を記録し、`route_e_stage` を `top_floor_entered` に更新するようにした。
- 最上階画面に小さな鍵穴ホットスポットと短いメッセージ表示だけを追加し、画面全体をクリック領域にしない構造にした。
- 鍵なし接触では `形は合っている。`、続けて `ここには、まだ何もありません。` を表示し、以後の再接触では短く `反応はありません。` のみを表示するようにした。
- 鍵所持状態では `keyhole_state = "ready"` に更新し、制作物04用の `startAnnihilationKeyUse()` / `kyoukai:route-e-keyhole-ready` へ接続するだけに留めた。

未実装として残す内容:
- 消滅の鍵の正式な取得、使用確認、挿入/回転/消費演出、404演出、逆観測室への本遷移、Route_E完了処理は制作物04以降で扱う。

確認内容:
- 最上階開放条件、入室記録、鍵穴状態、鍵なしメッセージ、鍵あり接続フック、PC/スマホ向けホットスポット最小サイズをテスト対象に追加した。

この進捗表は、各番号の仕様を受領し、実装と確認が完了した時点でのみ更新する。

## 事前準備

受領日: 2026-07-11  
仕様名: KYOUKAI終幕実装・事前指示書  
状態: 完了  
変更ファイル: なし  
追加ファイル: `docs/KYOUKAI_ENDING_IMPLEMENTATION_LOG.md`  
実装内容: 最終ルート本体は実装せず、既存構造、依存関係、変更候補ファイルを整理した。  
既存仕様への影響: なし。コード、シナリオ、素材、状態フラグは未変更。  
保存データへの影響: なし。localStorageキーやスキーマは未変更。  
確認内容: 下記の依存関係整理を参照。  
未解決事項: 制作物1から10まで未受領。  
次の番号へ進める状態か: はい。制作物1「最終ルートの名前・到達条件・終了条件」を受領可能。

## 依存関係整理

### Route_AからRoute_Dの完了判定

- 定義元: `static/kyoukai-scenario-events.js`, `data/scenarios/route_a.json` から `route_d.json`
- 各Routeは `route_status.<route_id> === "completed"` で完了判定される。
- 各Routeの完了条件は、電話イベント、部屋イベント、管理人帰還イベントの `event_completed` 群。
- Route完了時は `set_route_status`, `set_active_route: null`, `increment_counter: completed_scenario_count` が実行される。
- Route_A完了で `floor_04`、Route_B完了で `floor_05`、Route_C完了で `floor_06` を開放する。
- Route_D完了では新規階層を開放しない。

### active_route_id

- 定義元: `static/kyoukai-scenario.js`
- 初期値は `null`。
- 電話イベント受諾後、各Route開始時に `set_active_route` で対象Route IDへ更新される。
- 管理人帰還イベント完了時に `null` へ戻る。
- 次Route開始条件では `active_route_equals: null` を使う。

### completed_scenario_count

- 定義元: `static/kyoukai-scenario.js`, `static/kyoukai-scenario-events.js`
- 初期値は `0`。
- Route_AからRoute_Dの管理人帰還イベントで1ずつ加算される。
- Route_D完了後は通常どおり `4` になる想定。

### シナリオモードと自由見学モード

- 定義元: `static/kyoukai-scenario.js`
- `mode` が未設定の状態で最初に入った部屋によって決まる。
- 最初の部屋が `kanrinin` の場合は `scenario`。
- それ以外の部屋の場合は `free`。
- `home`, `elevator`, `floor` は passiveRooms として初期モード判定から除外される。
- 自由見学モードでは全通常部屋を開放する処理がある。

### 管理人室への再入室検知

- 定義元: `static/kyoukai-scenario.js`
- `markRoomEntered(roomId)` が `room_entry_history` に `{ room_id, at }` を追加する。
- `room_reentered_after_event` は対象イベント完了時刻より後に `kanrinin` へ入室した履歴があるかで判定する。
- `room_entered_after_event` は `currentRoomId` と `last_completed_event_id` の一致で判定する。

### 赤電話の20秒着信制御

- 定義元: `static/kanrinin.js`, `static/kyoukai-scenario.js`, `static/kyoukai-scenario-events.js`
- `PHONE_CHECK_DELAY_MS = 20000`。
- 管理人室で `schedulePhoneCheck()` が `startPhoneWait()` を呼び、20秒経過後に `getNextPhoneEvent()` を評価する。
- 各電話イベント側にも `room_stay_seconds >= 20` の要件がある。
- 着信音は既存では `/static/audio/kanrinin/red-phone-ring.mp3`。

### 最上階のロック状態

- 定義元: `static/kyoukai-building-data.js`, `static/kyoukai-scenario.js`, `static/kyoukai-floor.js`, `static/kyoukai-elevator.js`
- `topFloorRoom` は通常 `rooms` 配列とは分離されている。
- `getTopFloorRoom()` が通常部屋の最大階 + 1 を最上階として自動算出する。
- `topFloorRoom.defaultState` は現在 `locked`。
- `createDefaultState()` には `top_floor_unlocked: false` があるが、現状このフラグを使った開放処理は未実装。
- `canEnterRoom()` は `locked` を許可状態に含めないため、シナリオモードでは最上階は入れない。

### 鍵ボックスと消滅の鍵

- 定義元: `templates/kanrinin.html`, `static/kanrinin.js`, `static/kanrinin.css`, `data/rooms/kanrinin.md`
- `keyBoxArea` は鍵ボックスモーダルを開く。
- `annihilationKeyArea` は即時に `runAnnihilation()` を起動する。
- 現状、消滅の鍵は確認ダイアログなしで「管理人が鍵を回しました。」を表示し、暗転後 `/kanrinin/deleted` へ遷移する。
- `annihilation_key_obtained` は状態初期値にあるが、現状の鍵操作では更新されない。

### 404演出

- 定義元: `templates/404.html`, `static/kyoukai-404.js`, `static/kyoukai-404.css`, `main.py`
- 通常の404と消滅の鍵からの `/kanrinin/deleted` は同じ404テンプレートを使う。
- `kyoukai_404_count` に訪問回数を保存し、回数に応じて文字崩壊が進む。
- 終幕演出として404を使う場合は、通常404と区別する状態判定が今後必要。

### 逆観測室

- 定義元: `templates/observer.html`, `static/observer.js`, `static/observer.css`, `data/rooms/observer.md`
- `/observer` は既存実装あり。
- 世界観上は「観測する側と観測される側の逆転」が完成する場所。
- `/ma` への隠し導線がある。
- `data/rooms/observer.md` では終幕向けのセレクタ、座標、推奨尺は未設定。

### 管理日誌ページ追加方式

- 定義元: `static/kanrinin-diary.json`, `static/kanrinin.js`, `static/kyoukai-scenario-events.js`
- 静的な基本日誌は `static/kanrinin-diary.json` に配列で保存される。
- Route進行で追加される日誌は `static/kyoukai-scenario-events.js` の `diaryEntries` と `diary_entry_ids` を `mergeScenarioDiaryPages()` で結合する。
- 終幕ページは、静的JSONへ追加する方法と、シナリオイベントの `append_diary_entry` で追加する方法の両方が候補。

### localStorage

- 主キー: `kyoukai_scenario_state_v1`
- 定義元: `static/kyoukai-scenario.js`
- `normalizeState()` が既存保存データに対してデフォルト値を補完する。
- 現在の `schema_version` は `1`。
- 既に存在する終幕候補フラグ:
  - `final_route_available`
  - `top_floor_unlocked`
  - `annihilation_key_obtained`
  - `top_floor_keyhole_active`
- 上記フラグは初期化されるが、正式な遷移・効果処理はまだない。

## 変更候補ファイル

番号別仕様を受領した後に、変更候補となるファイルは以下。

- `docs/境界ワールド.md`
- `data/kyoukai_world.md`
- `data/scenarios/route_*.json`
- `static/kyoukai-scenario-events.js`
- `static/kyoukai-scenario.js`
- `static/kyoukai-building-data.js`
- `static/kyoukai-floor.js`
- `static/kyoukai-elevator.js`
- `templates/top-floor.html`
- `data/rooms/top-floor.md`
- `templates/kanrinin.html`
- `static/kanrinin.js`
- `static/kanrinin.css`
- `static/kanrinin-diary.json`
- `data/rooms/kanrinin.md`
- `templates/observer.html`
- `static/observer.js`
- `static/observer.css`
- `data/rooms/observer.md`
- `templates/404.html`
- `static/kyoukai-404.js`
- `static/kyoukai-404.css`
- `tests/test_route_a_scenario.py`
- `tests/test_home_entrances.py`
- 必要に応じて新規テストファイル

## 製作物01

受領日: 2026-07-11  
仕様名: 最終ルートの名前・到達条件・終了条件  
状態: 完了  
変更ファイル:
- `docs/境界ワールド.md`
- `static/kyoukai-scenario-events.js`
- `static/kyoukai-scenario.js`
- `static/kanrinin.js`
- `docs/KYOUKAI_ENDING_IMPLEMENTATION_LOG.md`

追加ファイル:
- `data/scenarios/route_e.json`
- `tests/test_route_e_scenario.py`

実装内容:
- Route_E「観測の完了」の基本定義を追加した。
- Route_Eの内部IDを `route_e`、種別を `final`、`is_final_route: true` として登録した。
- Route_AからRoute_Dがすべて completed、シナリオモード、`active_route_id === null`、`final_route_available === true`、`ending_completed !== true` のときだけRoute_E電話イベントが候補になるようにした。
- Route_D完了時にRoute_Eを自動開始せず、`route_e` を available、`final_route_available` を true にする待機状態を追加した。
- Route_D完了後の管理人室再入室と20秒待機をRoute_E電話イベントの条件にした。
- 電話を取った時点で `route_e` を active、`active_route_id` を `route_e` にするため、Route_E専用の `start_effects` を追加した。
- 最終電話本文、発信者、最上階・鍵穴・消滅の鍵・逆観測室・管理日誌本文は未実装のまま、後続仕様を差し込めるイベントIDだけを骨格として定義した。
- `route_e_stage`, `ending_completed`, `kyoukai_completed_at` の保存土台と欠損キー補完を追加した。
- Route_E待機中に管理人室を20秒以内に離れた場合、再入室で20秒を測り直せるよう、Route_E待機状態だけ `phone_wait_started_at` をリセットする処理を追加した。

既存仕様への影響:
- Route_AからRoute_Dの会話文、イベントID、開始条件、完了条件は変更していない。
- Route_D完了処理にはRoute_E待機状態を作る効果だけを追加した。
- 自由見学モードでは `getNextPhoneEvent()` がシナリオモード以外を除外するため、Route_Eは発生しない。
- 最上階はRoute_E電話完了後に `top_floor_unlocked` が true になる土台を追加したが、鍵穴イベントは未実装。

保存データへの影響:
- `normalizeState()` により、既存の `kyoukai_scenario_state_v1` に新規キーがなくても安全に補完される。
- localStorageのキー名と `schema_version` は変更していない。
- 既存Route_AからRoute_Dの保存状態は維持される。

確認内容:
- `tests/test_route_e_scenario.py` を追加し、Route_E定義、開始条件、Route_D完了後の待機化、管理人室再入室と20秒条件、電話取得時active化、完了条件骨格、欠損キー補完を確認する。
- 既存のRoute_A系テスト、ホーム/エレベーター系テスト、Route_B/C/D系テストも実行対象とする。

未解決事項:
- 最終電話の会話・発信者・着信表示は制作物02待ち。
- 最上階・鍵穴イベントは制作物03待ち。
- 消滅の鍵の正式仕様は制作物04で完了。
- 逆観測室の終幕演出・最終文は制作物05で完了。
- 管理日誌の終幕ページ本文は制作物06で完了。制作物07で正式保存設計を統合予定。
- 状態フラグの正式保存設計と再訪演出は制作物07待ち。

次の番号へ進める状態か: はい。制作物02「最終電話の会話・発信者・着信仕様」を受領可能。

## 後続仕様まで変更しないもの

- 最終電話の発信者と会話文
- 最上階の正式名称
- 鍵穴の操作内容
- 消滅の鍵の最終的な意味
- 逆観測室の最終文
- 管理日誌の終幕本文
- 終幕後の再訪開始位置は制作物07で通常開始・再訪仕様を確定。
- 終幕用画像、音、UI
- SNS/Shorts/告知文

## 制作物06

受領日: 2026-07-13
仕様名: 管理日誌の終幕ページ
状態: 実装完了

変更内容:

- 管理人室帰還後にのみ `観測完了記録` を解放するRoute_E専用の日誌イベントを追加。
- 終幕ページの正式本文を既存の日誌モーダルへ末尾追加し、既存4ページの順序と本文を維持。
- 初回閲覧時に既読状態、閲覧日時、Route_E完了、`ending_variant`、`kyoukai_completed_at` を保存。
- 管理人室更新通知と完了通知を一度だけ表示し、終幕後の再閲覧では完了処理を再実行しない。
- 既存保存データの欠損キーを `normalizeState()` で補完。

確認内容:

- JavaScript構文チェック、Route_E JSONの読み込み、`git diff --check` を通過。
- 全69テストを通過。

未解決事項:

- 制作物07で正式保存設計と終幕後の再訪仕様を統合済み。

## 制作物07

受領日: 2026-07-13
仕様名: 状態フラグ・localStorage・終幕後再訪設計
状態: 実装完了

変更内容:

- 既存キー `kyoukai_scenario_state_v1` を維持したまま、保存内部バージョンを `schema_version = 2` に更新。
- 旧保存データ、欠損値、旧ステージ名、ネスト形式の状態を読み込み時に補完・移行。
- Route_E完了済み状態を優先して、鍵・最上階・逆観測室・管理日誌・完了日時を整合修復。
- UI操作ロックを保存対象から除外し、`processing` 状態を再開可能な鍵穴状態へ復旧。
- localStorage破損時に `kyoukai_scenario_state_corrupt_backup` へ退避し、保存失敗を既存通知へ接続。
- 終幕後は赤電話を停止し、鍵ボックス、鍵穴、最上階、逆観測室、終幕日誌を再訪可能にした。
- 開発環境限定の `resetRouteEForDevelopment()` を追加。本番UIからは呼び出さない。

保存データへの影響:

- Route_A〜Route_D、既存アイテム、日誌、部屋状態は維持。
- Route_E完了後の `completed_scenario_count` は既存値を減らさず、最低5を保証。

確認内容:

- JavaScript構文チェック、JSON検証、`git diff --check` を通過。
- 全69テストを通過。

未解決事項:

- なし。制作物08「終幕用画像・音・UI素材仕様」を受領可能。

## 制作物08

受領日: 2026-07-27
仕様名: 終幕用画像・音・UI素材仕様
状態: 実装完了

変更ファイル:
- `static/top-floor.js`
- `static/space.css`
- `static/observer.js`
- `static/observer.css`
- `tests/test_route_e_scenario.py`
- `docs/KYOUKAI_ENDING_ASSET_LOG.md`

実装内容:
- 新規背景・新規BGM・外部素材を追加せず、既存背景とCSS/DOM演出を再利用。
- 最上階の鍵穴に6状態の状態クラスを付与。
- CSS生成の鍵ビジュアルによる挿入・一回転演出を維持し、reduced motion時は即時表示へ短縮。
- 逆観測室の終幕状態と終幕後再訪状態を分離し、通常再訪で終幕演出を再実行しないようにした。

既存仕様への影響:
- Route_AからRoute_D、通常の逆観測室、管理人室、赤電話音、日誌UIは変更していない。
- 新規音源・新規画像差分は追加していない。

確認内容:
- 終幕素材台帳へ実ファイル、CSS生成素材、再利用素材、PC/モバイル、フォールバックを記録。
- 鍵穴状態、reduced motion、終幕後逆観測室クラス、外部素材非追加をテスト対象へ追加。

未解決事項:
- なし。制作物09「Codex向け統合実装指示書・最終テスト条件」を受領可能。

## 作業時の注意

- 現在の作業ツリーには、このログ以外の未コミット差分が存在する。終幕実装では無関係な差分を混ぜない。
- 各制作物は可能な限り1番号1コミットで管理する。
- Route_AからRoute_Dの既存進行に触れる場合は、変更理由と互換性への影響を必ずこのログへ追記する。
- 通常の404動作と終幕演出の404利用は混同しない。
- PCとスマートフォンの両方で確認する。モバイル縦画面を優先する。

## 製作物番号テンプレート

```text
## 製作物番号

受領日:
仕様名:
状態:
変更ファイル:
追加ファイル:
実装内容:
既存仕様への影響:
保存データへの影響:
確認内容:
未解決事項:
次の番号へ進める状態か:
```
