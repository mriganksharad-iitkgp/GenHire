import array
import math
import unittest
from unittest.mock import MagicMock

from services.live_transcription_service import LiveTranscript, append_transcript, has_speech_energy


def pcm(seconds):
    return array.array("h", (int(3000 * math.sin(i * .11)) for i in range(int(seconds * 16000)))).tobytes()


class LiveCaptionsTests(unittest.TestCase):
    def test_overlap_preserves_text_and_silence_does_not_invent_words(self):
        self.assertEqual(append_transcript("I built a hiring platform", "hiring platform using Python."), "I built a hiring platform using Python.")
        self.assertFalse(has_speech_energy(bytes(6400)))
        self.assertTrue(has_speech_energy(pcm(.2)))

    def test_ordered_audio_finishes_and_releases_bounded_worker(self):
        emit, recognize = MagicMock(), MagicMock(side_effect=["I built a hiring platform", "hiring platform using Python"])
        stream = LiveTranscript("one", "owned-session", recognize, emit, lambda: True)
        self.assertTrue(stream.start())
        audio = pcm(4)
        packets = [audio[i:i + 6400] for i in range(0, len(audio), 6400)]
        # A native handler may briefly run out of order; this does not lose PCM.
        self.assertTrue(stream.add(1, packets[1])); self.assertTrue(stream.add(0, packets[0]))
        self.assertTrue(stream.add(0, packets[0]))
        for sequence, packet in enumerate(packets[2:], 2):
            self.assertTrue(stream.add(sequence, packet))
        result = stream.finish(len(packets) - 1)
        self.assertTrue(result["complete"])
        self.assertEqual(result["transcript"], "I built a hiring platform using Python")
        self.assertEqual(recognize.call_count, 2)
        self.assertTrue(stream.done.is_set())

    def test_gap_invalid_audio_and_closed_session_never_become_complete(self):
        stream = LiveTranscript("two", "owned-session", MagicMock(), MagicMock(), lambda: False)
        self.assertFalse(stream.add(0, b"odd"))
        self.assertFalse(stream.add(True, bytes(6400)))
        self.assertTrue(stream.start())
        self.assertTrue(stream.add(0, pcm(.2)))
        result = stream.finish(2)
        self.assertFalse(result["complete"])
        stream.recognize.assert_not_called()

    def test_provider_failure_preserves_recording_fallback_contract(self):
        emit = MagicMock()
        stream = LiveTranscript("three", "owned-session", MagicMock(side_effect=RuntimeError("provider unavailable")), emit, lambda: True)
        self.assertTrue(stream.start())
        audio = pcm(3)
        for sequence, offset in enumerate(range(0, len(audio), 6400)):
            self.assertTrue(stream.add(sequence, audio[offset:offset + 6400]))
        self.assertFalse(stream.finish(14)["complete"])
        self.assertIn("recorded answer", emit.call_args.args[0]["error"])
