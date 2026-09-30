import numpy as np

from agent.ai.detector import BoundingBox, Detection
from agent.ai.processor import EventPolicy
from agent.ai.tracking import IoUTracker
from agent.video.overlay import OverlayRenderer, format_label


def det(x, cls="person", conf=0.9, track=None):
    return Detection(0, cls, conf, BoundingBox(x, 10, x + 50, 110), track_id=track)


def test_iou_tracker_keeps_ids_stable():
    t = IoUTracker()
    a = t.update([det(0), det(200, "car")], timestamp=0.0)
    b = t.update([det(5), det(205, "car")], timestamp=0.2)
    assert [d.track_id for d in a] == [d.track_id for d in b] == [1, 2]
    c = t.update([det(400)], timestamp=0.4)  # far away -> new object
    assert c[0].track_id == 3


def test_tracker_follows_small_fast_objects():
    t = IoUTracker()
    narrow = [Detection(1, "bicycle", 0.9, BoundingBox(x, 100, x + 30, 180)) for x in (0, 40, 80, 120)]
    ids = [t.update([d], i * 0.2)[0].track_id for i, d in enumerate(narrow)]
    assert ids == [1, 1, 1, 1]  # moves > its own width per inference, IoU = 0, still one track


def test_iou_tracker_expires_tracks():
    t = IoUTracker(max_age_seconds=1.0)
    t.update([det(0)], 0.0)
    assert t.update([det(0)], 5.0)[0].track_id == 2


def test_event_policy_new_tracks_only():
    p = EventPolicy(cooldown_seconds=5)
    assert len(p.triggers([det(0, track=1), det(100, track=2)])) == 2
    assert p.triggers([det(0, track=1), det(100, track=2)]) == []
    assert [d.track_id for d in p.triggers([det(0, track=1), det(300, track=3)])] == [3]


def test_event_policy_class_cooldown_without_tracking():
    now = [0.0]
    p = EventPolicy(cooldown_seconds=5, clock=lambda: now[0])
    assert len(p.triggers([det(0)])) == 1
    assert p.triggers([det(0)]) == []
    now[0] = 6
    assert len(p.triggers([det(0)])) == 1


def test_overlay_draws_box_and_label():
    d = Detection(0, "person", 0.95, BoundingBox(20, 20, 120, 150), track_id=123)
    assert format_label(d) == "Person 95% #123"
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    OverlayRenderer().draw(img, [d])
    assert img.any()
    scaled = np.zeros((100, 100, 3), dtype=np.uint8)
    OverlayRenderer().draw(scaled, [d], 0.5, 0.5)  # detection coords mapped to a smaller output
    assert scaled[10:76, 10:61].any()
