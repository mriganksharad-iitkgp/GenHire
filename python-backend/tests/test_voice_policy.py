import os
import unittest
from unittest.mock import patch
from services.interview_voice_policy import voice_policy


class VoicePolicyTests(unittest.TestCase):
    def test_defaults_and_experiment_overrides_are_safe_public_numbers(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(voice_policy()["silence_seconds"], 5)
            self.assertEqual(voice_policy()["initial_wait_seconds"], 10)
        with patch.dict(os.environ, {"INTERVIEW_SILENCE_SECONDS": "7", "INTERVIEW_INITIAL_WAIT_SECONDS": "20"}):
            self.assertEqual(voice_policy()["silence_seconds"], 7)
            self.assertEqual(voice_policy()["initial_wait_seconds"], 20)

    def test_invalid_settings_cannot_disable_or_extend_recording_forever(self):
        with patch.dict(os.environ, {"INTERVIEW_SILENCE_SECONDS": "nan", "INTERVIEW_INITIAL_WAIT_SECONDS": "bad", "INTERVIEW_MAX_ANSWER_SECONDS": "9999"}):
            policy = voice_policy()
            self.assertEqual(policy["silence_seconds"], 5)
            self.assertEqual(policy["initial_wait_seconds"], 10)
            self.assertEqual(policy["max_answer_seconds"], 180)
