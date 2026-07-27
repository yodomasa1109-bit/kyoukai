# KYOUKAI 終幕素材台帳

作成日: 2026-07-27
対象: 終幕制作物08

## 方針

終幕専用の大型画像、外部素材、新規BGMは追加しない。既存素材とCSS/DOMの状態表現を優先し、画像や音の読み込みに失敗しても状態更新と文章進行を継続する。

## 素材一覧

| 素材名 | 用途 | 既存/新規 | 元ファイル・配置先 | 使用状態 | PC/スマートフォン | 代替処理 |
|---|---|---|---|---|---|---|
| 最上階背景 | Route_E最上階 | 既存 | `static/images/top-floor/room-9x16.png` | unlocked / completed | 同一画像をレスポンシブ表示 | 画像表示失敗時も鍵穴UIを維持 |
| 鍵穴 | 鍵穴ホットスポット | CSS/DOM | `static/space.css`, `templates/top-floor.html` | inactive / available / waiting_for_key / ready / processing / completed | 44px以上の操作領域、画面中央配置 | base背景と状態クラスで継続 |
| 消滅の鍵 | 鍵挿入演出 | CSS/DOM | `static/top-floor.js`, `static/space.css` | visible / inserted / turned | 画面内の鍵穴へ遷移 | ビジュアルを省略して状態更新を継続 |
| 逆観測室背景 | 通常・終幕・再訪 | 既存 | `static/images/observer/observer_bg_morning.png`, `observer_bg_night.png` | normal / route_e_final / post-route-e | 既存背景を維持 | テキストのみで終幕を成立 |
| 管理人室背景 | 終幕後帰還 | 既存 | `static/images/kanrinin/kanrinin-room-9x16.png` | post-route-e | 既存UIで表示 | 背景差分なし、状態と通知で表現 |
| 赤電話着信音 | 最終電話 | 既存 | `static/audio/kanrinin/red-phone-ring.mp3` | Route_E電話中のみ | 既存音量設定に従う | 再生失敗・ミュートでも進行 |
| 管理日誌UI | 終幕ページ | 既存 | `templates/kanrinin.html`, `static/kanrinin.js`, `static/kanrinin-diary.json` | final diary | 既存モーダル、モバイルはスクロール | 本文表示を継続 |
| 暗転 | 最上階から逆観測室、帰還 | 既存CSS | `static/space.css`, `static/observer.css` | transition / returning | 全画面レイヤー | reduced motionでは即時切替 |

## 新規追加しなかったもの

- `top-floor-entrance-*.webp`
- `top-floor-keyhole-*.webp`
- `annihilation-key.webp/png`
- `observer-route-e-reversed.webp`
- `kanrinin-room-keybox-empty.webp`
- 終幕専用SE、終幕BGM、動画、GIF、外部素材

既存画像またはCSS/DOMで仕様を満たすため、重複ファイルを作成していない。音源の再生成功をイベント完了条件にしていない。

## アクセシビリティ・性能

- `prefers-reduced-motion: reduce` では鍵移動、回転、暗転、逆観測室アニメーションを短縮または停止し、進行状態は維持する。
- 状態は色だけでなく、反応、透明度、操作可否、文言、状態クラスで示す。
- 終幕専用画像の初回一括読み込みは行わない。新規素材がないため追加通信も発生しない。
- 鍵穴、テキスト送り、帰還ボタンは既存UIの操作領域を使用する。帰還ボタンは44px以上。
