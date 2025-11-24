import os
import torch
import librosa
import cv2
import warnings
import logging
from pyannote.audio import Pipeline
from ultralytics import YOLO

# Configure logging
logger = logging.getLogger(__name__)

class RecordingAnalyzer:
    def __init__(self):
        self.hf_token = "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"  # Your provided token
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
    def analyze_speakers(self, audio_path, duration=300):
        """
        Analyzes the number of speakers in the audio file.
        """
        if not os.path.exists(audio_path):
            print(f"Error: Audio file not found at {audio_path}")
            return

        print("\n--- Starting Speaker Analysis ---")
        print(f"Using device: {self.device}")

        # 1. Load Pipeline
        try:
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token
            ).to(self.device)
        except Exception as e:
            print(f"Error loading pipeline: {e}")
            return

        # 2. Load Audio
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                waveform, sample_rate = librosa.load(
                    audio_path, 
                    sr=16000,
                    mono=True,
                    duration=duration
                )
            
            waveform_tensor = torch.from_numpy(waveform).to(self.device).unsqueeze(0)
            audio_input = {"waveform": waveform_tensor, "sample_rate": sample_rate}

            # 3. Run Diarization
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                diarization = pipeline(audio_input)

            # 4. Extract Results
            speaker_set = set()
            annotation = None
            
            if hasattr(diarization, "speaker_diarization"):
                annotation = diarization.speaker_diarization
            elif hasattr(diarization, "annotation"):
                annotation = diarization.annotation
            
            if annotation:
                for turn, _, speaker in annotation.itertracks(yield_label=True):
                    speaker_set.add(speaker)
            
            # PRINT RESULT 1: Number of people
            print(f"\n--- 🚀 SPEAKER RESULT 🚀 ---")
            print(f"There are {len(speaker_set)} people speaking in the first {duration} seconds.")
            
        except Exception as e:
            print(f"Error during speaker analysis: {e}")

    def analyze_video_objects(self, video_path):
        """
        Analyzes video frames to find objects other than 'person'.
        """
        if not os.path.exists(video_path):
            print("Error: Video file not found.")
            return

        print("\n--- Starting Video Object Analysis ---")
        model = YOLO('yolov8n.pt')
        cap = cv2.VideoCapture(video_path)
        
        detected_other_objects = set()
        frame_count = 0
        
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break
            
            # Optimization: Process every 30th frame (approx once per second) 
            # to keep it faster, otherwise it will take too long.
            frame_count += 1
            if frame_count % 30 != 0:
                continue

            results = model(frame, verbose=False)
            
            # Iterate through detections
            for r in results:
                for box in r.boxes:
                    # Get class ID and name
                    cls_id = int(box.cls[0])
                    class_name = model.names[cls_id]
                    
                    # Check if it is NOT a person
                    if class_name != 'person':
                        detected_other_objects.add(class_name)

        cap.release()
        
        # PRINT RESULT 2: What else was observed
        print(f"\n--- 🚀 VIDEO OBJECT RESULT 🚀 ---")
        if detected_other_objects:
            print("Observed objects other than person:", ", ".join(detected_other_objects))
        else:
            print("Observed objects other than person: None")

    def run_full_analysis(self, filepath):
        """Helper to run both analyses"""
        print(f"\n[Analysis] Processing file: {filepath}")
        # Run Speaker Analysis
        self.analyze_speakers(filepath)
        # Run Video Object Analysis
        self.analyze_video_objects(filepath)
        print("[Analysis] Processing complete.\n")