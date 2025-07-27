import os
import cv2
import numpy as np
from gack.face_recog import FaceRecognizer

def _make_face(val: int) -> np.ndarray:
    img = np.full((200, 200), val, dtype=np.uint8)
    return img

def test_face_recognizer_basic(tmp_path):
    faces_dir = tmp_path / "faces"
    alice = faces_dir / "alice"
    bob = faces_dir / "bob"
    alice.mkdir(parents=True)
    bob.mkdir(parents=True)
    cv2.imwrite(str(alice / "a.png"), _make_face(50))
    cv2.imwrite(str(bob / "b.png"), _make_face(80))
    fr = FaceRecognizer(str(faces_dir))
    assert len(fr.label_map) == 2

