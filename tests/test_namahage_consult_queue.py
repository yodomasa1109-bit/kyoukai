import asyncio
import json
import unittest

import main


def response_json(response):
    return json.loads(response.body.decode("utf-8"))


class NamahageConsultQueueTests(unittest.TestCase):
    def setUp(self):
        self.session = "queue-test"
        main.NAMAHAGE_CONSULTS.pop(self.session, None)
        main.NAMAHAGE_CONSULT_QUEUES.pop(self.session, None)

    def tearDown(self):
        main.NAMAHAGE_CONSULTS.pop(self.session, None)
        main.NAMAHAGE_CONSULT_QUEUES.pop(self.session, None)

    def run_async(self, awaitable):
        return asyncio.run(awaitable)

    def test_enqueued_consult_becomes_current_on_next(self):
        first = {
            "session": self.session,
            "visible": True,
            "title": "現在の相談",
            "summary": "現在表示している相談です。",
        }
        second = {
            "session": self.session,
            "enqueue": True,
            "title": "次の相談",
            "summary": "待機列に入れる相談です。",
        }

        self.run_async(main.set_namahage_avatar_consult(first))
        queued_response = self.run_async(main.set_namahage_avatar_consult(second))
        queued = response_json(queued_response)

        self.assertTrue(queued["queued"])
        self.assertEqual(queued["queueLength"], 1)
        self.assertEqual(queued["consult"]["title"], "現在の相談")

        next_response = self.run_async(
            main.show_next_namahage_avatar_consult({"session": self.session})
        )
        next_payload = response_json(next_response)

        self.assertEqual(next_response.status_code, 200)
        self.assertEqual(next_payload["consult"]["title"], "次の相談")
        self.assertTrue(next_payload["consult"]["visible"])
        self.assertEqual(next_payload["queueLength"], 0)

    def test_next_with_empty_queue_keeps_current_consult(self):
        current = {
            "session": self.session,
            "visible": True,
            "title": "残す相談",
            "summary": "待機列が空でも表示を維持します。",
        }
        self.run_async(main.set_namahage_avatar_consult(current))

        response = self.run_async(
            main.show_next_namahage_avatar_consult({"session": self.session})
        )
        payload = response_json(response)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(payload["error"], "queue empty")
        self.assertEqual(payload["consult"]["title"], "残す相談")
        self.assertEqual(payload["queueLength"], 0)

    def test_enqueue_requires_title_and_summary(self):
        response = self.run_async(
            main.set_namahage_avatar_consult(
                {"session": self.session, "enqueue": True, "title": ""}
            )
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response_json(response)["error"], "title and summary required")
        self.assertNotIn(self.session, main.NAMAHAGE_CONSULT_QUEUES)


if __name__ == "__main__":
    unittest.main()
