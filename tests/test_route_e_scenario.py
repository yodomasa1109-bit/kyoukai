import json
import unittest
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]


class RouteEFoundationTests(unittest.TestCase):
    def setUp(self):
        self.route_e_json_path = BASE_DIR / "data" / "scenarios" / "route_e.json"
        self.route_e_json = json.loads(self.route_e_json_path.read_text(encoding="utf-8"))
        self.events_js = (BASE_DIR / "static" / "kyoukai-scenario-events.js").read_text(encoding="utf-8")
        self.scenario_js = (BASE_DIR / "static" / "kyoukai-scenario.js").read_text(encoding="utf-8")
        self.kanrinin_html = (BASE_DIR / "templates" / "kanrinin.html").read_text(encoding="utf-8")
        self.kanrinin_js = (BASE_DIR / "static" / "kanrinin.js").read_text(encoding="utf-8")
        self.top_floor_html = (BASE_DIR / "templates" / "top-floor.html").read_text(encoding="utf-8")
        self.top_floor_js = (BASE_DIR / "static" / "top-floor.js").read_text(encoding="utf-8")
        self.space_css = (BASE_DIR / "static" / "space.css").read_text(encoding="utf-8")
        self.observer_html = (BASE_DIR / "templates" / "observer.html").read_text(encoding="utf-8")
        self.observer_js = (BASE_DIR / "static" / "observer.js").read_text(encoding="utf-8")
        self.observer_css = (BASE_DIR / "static" / "observer.css").read_text(encoding="utf-8")

    def test_route_e_definition_is_final_route(self):
        self.assertEqual(self.route_e_json["route_id"], "route_e")
        self.assertEqual(self.route_e_json["name"], "観測の完了")
        self.assertEqual(self.route_e_json["type"], "final")
        self.assertTrue(self.route_e_json["is_final_route"])
        self.assertIn('route_id: "route_e"', self.events_js)
        self.assertIn('name: "観測の完了"', self.events_js)
        self.assertIn('type: "final"', self.events_js)
        self.assertIn("is_final_route: true", self.events_js)

    def test_route_e_requires_completed_standard_routes_and_scenario_mode(self):
        required_tokens = [
            '{ type: "mode_equals", value: "scenario" }',
            '{ type: "route_status_equals", route_id: "route_a", value: "completed" }',
            '{ type: "route_status_equals", route_id: "route_b", value: "completed" }',
            '{ type: "route_status_equals", route_id: "route_c", value: "completed" }',
            '{ type: "route_status_equals", route_id: "route_d", value: "completed" }',
            '{ type: "active_route_equals", value: null }',
            '{ type: "state_equals", key: "final_route_available", value: true }',
            '{ type: "state_not_equals", key: "ending_completed", value: true }',
        ]
        for token in required_tokens:
            with self.subTest(token=token):
                self.assertIn(token, self.events_js)

    def test_route_d_only_makes_route_e_available(self):
        self.assertIn('{ type: "set_route_status", route_id: "route_e", value: "available" }', self.events_js)
        self.assertIn('{ type: "set_state_value", key: "final_route_available", value: true }', self.events_js)
        self.assertIn('{ type: "set_state_value", key: "top_floor_unlocked", value: false }', self.events_js)
        self.assertIn('{ type: "set_state_value", key: "top_floor_keyhole_active", value: false }', self.events_js)
        self.assertIn('{ type: "enable_event", event_id: "route_e_phone_001" }', self.events_js)

    def test_route_e_phone_waits_for_kanrinin_reentry_and_twenty_seconds(self):
        self.assertIn('event_id: "route_e_phone_001"', self.events_js)
        self.assertIn('caller_id: "route_e_caller_001"', self.events_js)
        self.assertIn('caller_display_name: "記録なし"', self.events_js)
        self.assertIn('resident_type: "unknown_record"', self.events_js)
        self.assertIn('{ type: "room_reentered_after_event", room_id: "kanrinin", after_event_id: "route_d_manager_return_001" }', self.events_js)
        self.assertIn('{ type: "room_stay_seconds", room_id: "kanrinin", operator: ">=", value: 20 }', self.events_js)
        self.assertIn('{ type: "room_stay_seconds", room_id: "kanrinin", operator: ">=", value: 1.5 }', self.events_js)
        self.assertIn('type: "any_of"', self.events_js)
        self.assertIn("PHONE_RESUME_DELAY_MS = 1500", self.kanrinin_js)
        self.assertIn("PHONE_CHECK_DELAY_MS = 20000", self.kanrinin_js)
        self.assertIn("resetPhoneWait", self.kanrinin_js)

    def test_route_e_becomes_active_when_phone_is_accepted(self):
        self.assertIn("start_effects", self.events_js)
        self.assertIn('{ type: "set_route_status", route_id: "route_e", value: "active" }', self.events_js)
        self.assertIn('{ type: "set_active_route", route_id: "route_e" }', self.events_js)
        self.assertIn('{ type: "set_timestamp", key: "route_e_started_at" }', self.events_js)
        self.assertIn('{ type: "set_state_value", key: "route_e_phone_answered", value: true }', self.events_js)
        self.assertIn('{ type: "set_timestamp", key: "route_e_phone_answered_at" }', self.events_js)
        self.assertIn("event.start_effects", self.scenario_js)
        self.assertIn("applyEffect(state, effect)", self.scenario_js)
        self.assertIn("topFloorRoom.floor === number && state.top_floor_unlocked", self.scenario_js)

    def test_route_e_completion_skeleton_exists_with_final_phone_text(self):
        for event_id in [
            "route_e_phone_001",
            "route_e_phone_answer_001",
            "route_e_phone_dialogue_001",
            "route_e_phone_complete_001",
            "route_e_top_floor_001",
            "route_e_annihilation_key_001",
            "route_e_observer_final_001",
            "route_e_manager_return_001",
            "route_e_final_diary_001",
        ]:
            with self.subTest(event_id=event_id):
                self.assertIn(event_id, self.route_e_json_path.read_text(encoding="utf-8"))
                self.assertIn(event_id, self.events_js)
        for line in [
            "聞こえています。",
            "四つの記録を確認しました。",
            "受信。\\n保管。\\n生成。\\n集合。",
            "最上階を開きました。",
            "通話を終了します。",
        ]:
            with self.subTest(line=line):
                self.assertIn(line, self.events_js)
        self.assertIn('{ type: "set_state_value", key: "route_e_phone_completed", value: true }', self.events_js)
        self.assertIn('{ type: "set_timestamp", key: "route_e_phone_completed_at" }', self.events_js)
        self.assertIn('{ type: "set_state_value", key: "route_e_stage", value: "route_e_top_floor_unlocked" }', self.events_js)
        self.assertIn("最上階が開放されました。", self.kanrinin_js)
        self.assertIn("autoAdvance: !isFinalPhone", self.kanrinin_js)

    def test_state_defaults_and_missing_key_normalization_support_ending(self):
        for token in [
            'route_e_stage: "locked"',
            "top_floor_entered: false",
            "top_floor_entered_at: null",
            "top_floor_event_completed: false",
            "top_floor_keyhole_completed: false",
            'keyhole_state: "inactive"',
            "keyhole_touched: false",
            "keyhole_touched_without_key: false",
            "keyhole_interaction_lock: false",
            "route_e_started_at: null",
            "route_e_phone_answered: false",
            "route_e_phone_completed: false",
            "route_e_phone_completed_at: null",
            "route_e_phone_answer_lock: false",
            "ending_completed: false",
            "kyoukai_completed_at: null",
            "state_equals",
            "state_not_equals",
            "any_of",
            "set_state_value",
            "set_timestamp",
        ]:
            with self.subTest(token=token):
                self.assertIn(token, self.scenario_js)

    def test_deliverable_03_registers_top_floor_and_keyhole_events(self):
        for event_id in [
            "route_e_top_floor_unlock_001",
            "route_e_top_floor_enter_001",
            "route_e_keyhole_available_001",
            "route_e_keyhole_touch_without_key_001",
            "route_e_keyhole_ready_001",
            "route_e_keyhole_processing_001",
            "route_e_keyhole_complete_001",
        ]:
            with self.subTest(event_id=event_id):
                self.assertIn(event_id, self.route_e_json_path.read_text(encoding="utf-8"))
                self.assertIn(event_id, self.events_js)
        for token in [
            '{ type: "state_equals", key: "route_e_phone_completed", value: true }',
            '{ type: "state_equals", key: "top_floor_unlocked", value: true }',
            '{ type: "set_state_value", key: "top_floor_entered", value: true }',
            '{ type: "set_timestamp", key: "top_floor_entered_at" }',
            '{ type: "set_state_value", key: "route_e_stage", value: "top_floor_entered" }',
        ]:
            with self.subTest(token=token):
                self.assertIn(token, self.events_js)

    def test_top_floor_page_exposes_keyhole_without_full_screen_click_area(self):
        self.assertIn('aria-label="最上階"', self.top_floor_html)
        self.assertIn('data-top-floor-room', self.top_floor_html)
        self.assertIn('data-top-floor-keyhole', self.top_floor_html)
        self.assertIn('aria-label="鍵穴を調べる"', self.top_floor_html)
        self.assertIn('/static/top-floor.js?v=topfloor4', self.top_floor_html)
        self.assertIn('/static/space.css?v=topfloor3', self.top_floor_html)
        self.assertIn('.top-floor-room__keyhole', self.space_css)
        self.assertIn('width: max(44px', self.space_css)

    def test_top_floor_script_handles_entry_keyhole_and_future_key_use_hook(self):
        for token in [
            'active_route_id === "route_e"',
            'state.route_status?.route_e === "active"',
            "state.route_e_phone_completed === true",
            "state.top_floor_unlocked === true",
            "top_floor_entered = true",
            "route_e_top_floor_enter_001",
            "hasAnnihilationKey",
            "keyhole_state = \"waiting_for_key\"",
            "keyhole_state = \"ready\"",
            "route_e_keyhole_touch_without_key_001",
            "startAnnihilationKeyUse",
            "kyoukai:route-e-keyhole-ready",
            "形は合っている。",
            "ここには、まだ何もありません。",
            "反応はありません。",
        ]:
            with self.subTest(token=token):
                self.assertIn(token, self.top_floor_js)

    def test_deliverable_04_registers_annihilation_key_events(self):
        for event_id in [
            "route_e_annihilation_key_available_001",
            "route_e_annihilation_key_obtain_001",
            "route_e_annihilation_key_box_empty_001",
            "route_e_annihilation_key_ready_001",
            "route_e_annihilation_key_insert_001",
            "route_e_annihilation_key_turn_001",
            "route_e_annihilation_key_use_001",
            "route_e_annihilation_key_complete_001",
            "route_e_observer_transition_001",
            "route_e_observer_enter_001",
            "route_e_observer_text_001",
            "route_e_observer_reverse_001",
            "route_e_observer_complete_001",
        ]:
            with self.subTest(event_id=event_id):
                self.assertIn(event_id, self.route_e_json_path.read_text(encoding="utf-8"))
                self.assertIn(event_id, self.events_js)

    def test_annihilation_key_state_defaults_and_recovery_exist(self):
        for token in [
            "annihilation_key_obtained: false",
            "annihilation_key_obtained_at: null",
            "annihilation_key_used: false",
            "annihilation_key_used_at: null",
            "annihilation_key_consumed: false",
            "annihilation_key_obtain_lock: false",
            "annihilation_key_use_lock: false",
            'key_box_state: "contains_annihilation_key"',
            "observer_final_mode: false",
            "observer_final_event_started: false",
            "observer_final_event_started_at: null",
            "observer_final_event_completed: false",
            "observer_final_event_completed_at: null",
            "observer_reversed: false",
            "final_text_12_displayed: false",
            "return_control_unlocked: false",
            "user_selected_manager_return: false",
            "observer_final_transition_lock: false",
            "observer_final_text_lock: false",
            "observer_final_return_lock: false",
            'next.key_box_state = "empty"',
            'next.keyhole_state = hasAnnihilationKey(next) ? "ready" : "waiting_for_key"',
            "next.annihilation_key_use_lock = false",
            "next.annihilation_key_used = false",
            "next.annihilation_key_consumed = false",
            'item !== "annihilation_key"',
            'effect.type === "add_item"',
            'effect.type === "remove_item"',
        ]:
            with self.subTest(token=token):
                self.assertIn(token, self.scenario_js)

    def test_kanrinin_key_box_obtains_key_only_after_route_e_phone(self):
        for token in [
            'data-annihilation-key-item',
            "消滅の鍵",
            "canObtainAnnihilationKey",
            'state.mode === "scenario"',
            'state.active_route_id === "route_e"',
            'state.route_status?.route_e === "active"',
            "state.route_e_phone_completed === true",
            "state.ending_completed !== true",
            "state.annihilation_key_obtained !== true",
            "route_e_annihilation_key_obtain_001",
            "annihilationKeyItem.hidden = !canObtain",
            "消滅の鍵を持ち出した。",
            "鍵ボックスには、\\n何も残っていない。",
            "空になっている。",
        ]:
            with self.subTest(token=token):
                self.assertTrue(token in self.kanrinin_js or token in self.kanrinin_html)
        self.assertIn('{ type: "mode_equals", value: "scenario" }', self.events_js)
        self.assertIn('{ type: "state_equals", key: "route_e_phone_completed", value: true }', self.events_js)
        self.assertIn('{ type: "set_state_value", key: "annihilation_key_obtained", value: true }', self.events_js)
        self.assertIn('{ type: "set_timestamp", key: "annihilation_key_obtained_at" }', self.events_js)
        self.assertIn('{ type: "set_state_value", key: "route_e_stage", value: "annihilation_key_obtained" }', self.events_js)
        self.assertIn('{ type: "set_state_value", key: "key_box_state", value: "empty" }', self.events_js)
        self.assertIn('{ type: "add_item", item_id: "annihilation_key" }', self.events_js)

    def test_top_floor_uses_annihilation_key_without_confirmation_or_404(self):
        for token in [
            "canUseAnnihilationKey",
            "state.top_floor_entered === true",
            "state.annihilation_key_obtained === true",
            "state.annihilation_key_used !== true",
            "state.top_floor_keyhole_completed !== true",
            "鍵穴の奥で、\\n何かが待っている。",
            "消滅の鍵を差し込みます。",
            "beginAnnihilationKeyUse",
            "route_e_annihilation_key_insert_001",
            "route_e_annihilation_key_turn_001",
            "route_e_annihilation_key_use_001",
            "route_e_annihilation_key_complete_001",
            "消滅したものはありません。",
            "続いていた状態だけが、\\n終了しました。",
            'next.route_e_stage = "keyhole_completed"',
            'next.current_target_room_id = "observer"',
            "transitionToFinalObserver",
            "route_e_observer_transition_001",
            'window.location.href = "/observer"',
        ]:
            with self.subTest(token=token):
                self.assertIn(token, self.top_floor_js)
        self.assertIn('{ type: "set_state_value", key: "annihilation_key_used", value: true }', self.events_js)
        self.assertIn('{ type: "set_timestamp", key: "annihilation_key_used_at" }', self.events_js)
        self.assertIn('{ type: "set_state_value", key: "annihilation_key_consumed", value: true }', self.events_js)
        self.assertIn('{ type: "set_state_value", key: "top_floor_keyhole_completed", value: true }', self.events_js)
        self.assertIn('{ type: "set_state_value", key: "top_floor_event_completed", value: true }', self.events_js)
        self.assertIn('{ type: "set_target_room", room_id: "observer" }', self.events_js)
        self.assertNotIn('window.location.href = "/kanrinin/deleted"', self.top_floor_js)
        self.assertNotIn("confirm(", self.top_floor_js)

    def test_deliverable_05_observer_final_mode_text_and_return(self):
        for token in [
            '/static/observer.js?v=5',
            '/static/observer.css?v=5',
            "data-observer-room",
        ]:
            with self.subTest(token=token):
                self.assertIn(token, self.observer_html)
        for token in [
            "startFinalObserverMode",
            "canStartFinalObserver",
            'state.mode === "scenario"',
            'state.active_route_id === "route_e"',
            'state.route_status?.route_e === "active"',
            "state.annihilation_key_used === true",
            "state.top_floor_keyhole_completed === true",
            "state.top_floor_event_completed === true",
            "state.observer_final_event_completed !== true",
            "state.ending_completed !== true",
            "route_e_observer_enter_001",
            "route_e_observer_text_001",
            "route_e_observer_reverse_001",
            "route_e_observer_complete_001",
            "あなたは、\\nここを見ていました。",
            "観測は完了しました。",
            "KYOUKAIは、\\n記録として残ります。",
            "あなたは、\\nここから出ることができます。",
            "管理人室へ戻る",
            'window.location.href = "/kanrinin"',
        ]:
            with self.subTest(token=token):
                self.assertIn(token, self.observer_js)
        self.assertIn(".observer-room--route-e-final", self.observer_css)
        self.assertIn(".observer-final__text", self.observer_css)
        self.assertIn(".observer-final__return", self.observer_css)
        self.assertNotIn("confirm(", self.observer_js)
        self.assertNotIn("ending_completed = true", self.observer_js)

    def test_deliverable_05_events_keep_route_e_active_until_later_specs(self):
        for token in [
            '{ type: "set_state_value", key: "observer_final_mode", value: true }',
            '{ type: "set_state_value", key: "observer_final_event_started", value: true }',
            '{ type: "set_timestamp", key: "observer_final_event_started_at" }',
            '{ type: "set_state_value", key: "route_e_stage", value: "observer_active" }',
            '{ type: "set_state_value", key: "final_text_12_displayed", value: true }',
            '{ type: "set_state_value", key: "return_control_unlocked", value: true }',
            '{ type: "set_state_value", key: "observer_reversed", value: true }',
            '{ type: "set_state_value", key: "user_selected_manager_return", value: true }',
            '{ type: "set_state_value", key: "observer_final_event_completed", value: true }',
            '{ type: "set_timestamp", key: "observer_final_event_completed_at" }',
            '{ type: "set_state_value", key: "route_e_stage", value: "manager_return" }',
            '{ type: "set_target_room", room_id: "kanrinin" }',
        ]:
            with self.subTest(token=token):
                self.assertIn(token, self.events_js)
        self.assertIn('{ type: "set_route_status", route_id: "route_e", value: "completed" }', self.events_js)
        self.assertIn('{ type: "set_state_value", key: "ending_completed", value: true }', self.events_js)

    def test_deliverable_06_unlocks_final_diary_after_manager_return(self):
        for token in [
            "route_e_manager_return_complete_001",
            "route_e_diary_final_view_001",
            "route_e_complete_001",
            "manager_return_completed: false",
            "final_diary_entry_unlocked: false",
            "final_diary_entry_viewed: false",
            "final_diary_entry_unread: false",
            "final_diary_update_notice_shown: false",
            "manager_return_completed_at",
            "final_diary_entry_unlocked_at",
            "final_diary_entry_viewed_at",
            "観測完了記録",
            "観測対象の移動を確認。",
            "KYOUKAIは閉鎖されません。",
            "観測記録を完了しました。",
            "canUnlockFinalDiary",
            "completeRouteEFromDiary",
            "final_diary_view_lock",
        ]:
            with self.subTest(token=token):
                self.assertTrue(
                    token in self.events_js
                    or token in self.scenario_js
                    or token in self.kanrinin_js
                    or token in self.route_e_json_path.read_text(encoding="utf-8")
                )
        self.assertIn(
            '{ type: "room_reentered_after_event", room_id: "kanrinin", after_event_id: "route_e_observer_complete_001" }',
            self.events_js,
        )
        self.assertIn('{ type: "set_state_value", key: "final_diary_entry_unlocked", value: true }', self.events_js)
        self.assertIn('{ type: "set_state_value", key: "final_diary_entry_viewed", value: true }', self.events_js)
        self.assertIn('{ type: "set_route_status", route_id: "route_e", value: "completed" }', self.events_js)
        self.assertIn('{ type: "set_state_value", key: "ending_variant", value: "observation_completed" }', self.events_js)
        self.assertIn("static/kanrinin-diary.json", self.kanrinin_js)

    def test_deliverable_07_version_migration_and_revisit_guards(self):
        for token in [
            'var SCHEMA_VERSION = 2',
            'schema_version: SCHEMA_VERSION',
            'var ROUTE_E_STAGES',
            'var ROUTE_E_STATUSES',
            'kyoukai_scenario_state_corrupt_backup',
            'function persistState(state)',
            'function resetRouteEForDevelopment()',
            'resetRouteEForDevelopment: resetRouteEForDevelopment',
            'route_e_completed_at: null',
            'next.annihilation_key_obtain_lock = false',
            'next.observer_final_transition_lock = false',
            'next.route_e_complete_lock = false',
        ]:
            with self.subTest(token=token):
                self.assertIn(token, self.scenario_js)
        self.assertIn('"status_default": "locked"', self.route_e_json_path.read_text(encoding="utf-8"))
        self.assertIn('state.ending_completed === true', self.kanrinin_js)
        self.assertIn('showMessage("音はしない。", 1800)', self.kanrinin_js)
        self.assertIn('canVisitCompletedTopFloor', self.top_floor_js)
        self.assertIn('showMessage("閉じています。", 1800)', self.top_floor_js)
        self.assertIn('shouldResumeManagerReturn', self.observer_js)
        self.assertIn('観測は完了しています。', self.observer_js)

    def test_deliverable_08_reuses_assets_and_adds_safe_visual_states(self):
        asset_log = (BASE_DIR / "docs" / "KYOUKAI_ENDING_ASSET_LOG.md").read_text(encoding="utf-8")
        for token in [
            "static/images/top-floor/room-9x16.png",
            "static/images/observer/observer_bg_morning.png",
            "static/images/kanrinin/kanrinin-room-9x16.png",
            "static/audio/kanrinin/red-phone-ring.mp3",
            "top-floor-keyhole-*.webp",
            "observer-route-e-reversed.webp",
            "prefers-reduced-motion",
            "画像表示失敗時も鍵穴UIを維持",
        ]:
            with self.subTest(token=token):
                self.assertIn(token, asset_log)
        self.assertIn('const keyholeState = active ? ensureKeyholeState(state) : "inactive";', self.top_floor_js)
        self.assertIn('room.classList.toggle(`keyhole--${name}`, keyholeState === name);', self.top_floor_js)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.space_css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.observer_css)
        self.assertIn("observer-room--post-route-e", self.observer_js)
        self.assertIn("top-floor-room__use-key", self.space_css)


if __name__ == "__main__":
    unittest.main()
