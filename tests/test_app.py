import os
import unittest
from unittest.mock import patch

import app as chatbot


class ChatbotSmokeTests(unittest.TestCase):
    def setUp(self):
        self.client = chatbot.app.test_client()
        # Keep tests independent of a developer's real API key.
        self.key_patch = patch.dict(os.environ, {"GEMINI_API_KEY": ""})
        self.key_patch.start()

    def tearDown(self):
        self.key_patch.stop()

    def test_homepage_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SRIT Enquiry Assistant", response.data)

    def test_health_endpoint(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")
        self.assertTrue(response.get_json()["fallback_available"])

    def test_courses_question_works_without_ai_key(self):
        response = self.client.post("/api/chat", json={"message": "What courses and branches are listed at SRIT?"})
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["mode"], "knowledge")
        self.assertIn("Computer Science", body["answer"])
        self.assertIn("courses-offered", body["answer"])

    def test_fees_do_not_invent_amount(self):
        response = self.client.post("/api/chat", json={"message": "What is the fee amount?"})
        answer = response.get_json()["answer"]
        self.assertIn("does not", answer.lower())
        self.assertIn("fee-structure", answer)

    def test_blank_message_is_rejected(self):
        response = self.client.post("/api/chat", json={"message": "   "})
        self.assertEqual(response.status_code, 400)

    def test_contact_details(self):
        response = self.client.post("/api/chat", json={"message": "SRIT contact phone and email"})
        answer = response.get_json()["answer"]
        self.assertIn("hr@srit.ac.in", answer)
        self.assertIn("91-951 561 1111", answer)


if __name__ == "__main__":
    unittest.main()
