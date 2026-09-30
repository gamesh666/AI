import numpy as np
from agent.ai.detector import Detection
from agent.core.frame_queue import Frame

from aivms_sim.edge.mock_detector import DEFAULT_CLASSES, MockDetector


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _frame(w=1920, h=1080):
    return Frame(image=np.zeros((h, w, 3), dtype=np.uint8), seq=1)


def _run(det, clock, seconds, step=0.2, frame=None):
    frame = frame or _frame()
    out = []
    for _ in range(int(seconds / step)):
        clock.t += step
        out.append(det.detect(frame))
    return out


def test_output_has_exactly_the_yolo_detection_shape():
    clock = Clock()
    det = MockDetector(seed=7, clock=clock)
    det.load()
    batches = _run(det, clock, 20)
    found = [d for batch in batches for d in batch]
    assert found, "objects should appear within a few seconds"
    for d in found:
        assert type(d) is Detection  # the same type YoloDetector returns
        assert d.class_name in DEFAULT_CLASSES and d.class_id == DEFAULT_CLASSES[d.class_name]
        assert 0.3 <= d.confidence <= 0.99
        assert 0 <= d.bbox.x1 < d.bbox.x2 <= 1920 and 0 <= d.bbox.y1 < d.bbox.y2 <= 1080
        assert d.track_id is None  # track ids come from the (production) tracker, like with YOLO


def test_objects_appear_every_few_seconds_and_move():
    clock = Clock()
    det = MockDetector(seed=3, clock=clock, spawn_interval=(2, 3), lifetime=(20, 20), max_objects=4)
    det.load()
    first = det.detect(_frame())
    assert len(first) == 1  # spawned immediately
    clock.t += 1.0
    moved = det.detect(_frame())
    assert moved[0].bbox.x1 != first[0].bbox.x1
    counts = [len(b) for b in _run(det, clock, 12, step=1.0)]
    assert max(counts) >= 3 and max(counts) <= 4


def test_all_demo_classes_are_generated():
    clock = Clock()
    det = MockDetector(seed=11, clock=clock, spawn_interval=(0.5, 1.0), lifetime=(2, 3))
    det.load()
    names = {d.class_name for batch in _run(det, clock, 120) for d in batch}
    assert names == {"person", "car", "truck", "excavator"}


def test_class_ids_follow_the_model_labels_when_known():
    det = MockDetector(labels=["excavator", "person"], seed=1)
    assert det.class_id("excavator") == 0 and det.class_id("person") == 1
    assert det.class_id("car") == 2  # not in the model -> COCO id
