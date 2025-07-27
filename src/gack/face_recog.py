import os
import cv2
import numpy as np
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class FaceRecognizer:
    """Simple CPU-based face recognizer using OpenCV's LBPH algorithm."""

    def __init__(self, faces_dir: str):
        self.faces_dir = faces_dir
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.label_map = {}
        images = []
        labels = []
        label_id = 0
        for name in sorted(os.listdir(faces_dir)):
            person_dir = os.path.join(faces_dir, name)
            if not os.path.isdir(person_dir):
                continue
            added = False
            for img_name in os.listdir(person_dir):
                img_path = os.path.join(person_dir, img_name)
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                images.append(cv2.resize(img, (200, 200)))
                labels.append(label_id)
                added = True
            if added:
                self.label_map[label_id] = name
                label_id += 1
        if images:
            self.recognizer.train(images, np.array(labels))
            logger.info("Loaded %d known faces for recognition", len(self.label_map))
        else:
            logger.warning("No training images found for face recognition")
            self.recognizer = None

    def recognize_in_bbox(self, frame, bbox) -> Optional[str]:
        if self.recognizer is None:
            return None
        x1, y1, x2, y2 = map(int, bbox)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        roi_gray = gray[y1:y2, x1:x2]
        faces = self.face_cascade.detectMultiScale(roi_gray, scaleFactor=1.1, minNeighbors=5)
        for (x, y, w, h) in faces:
            face_img = roi_gray[y:y+h, x:x+w]
            face_img = cv2.resize(face_img, (200, 200))
            label, confidence = self.recognizer.predict(face_img)
            name = self.label_map.get(label)
            logger.debug("Face detected in bbox %s with label %s confidence %.2f", bbox, name, confidence)
            return name
        return None
