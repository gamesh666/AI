import threading
import time

import numpy as np

from agent.core.backoff import Backoff
from agent.core.frame_queue import BoundedFrameQueue, Frame
from agent.core.worker import Worker


def _frame(i: int) -> Frame:
    return Frame(image=np.zeros((2, 2, 3), dtype=np.uint8), seq=i)


def test_queue_is_bounded_and_drops_oldest():
    q = BoundedFrameQueue(maxsize=3)
    for i in range(10):
        q.put(_frame(i))
    assert len(q) == 3 and q.dropped == 7
    assert [q.get(0).seq for _ in range(3)] == [7, 8, 9]
    assert q.get(timeout=0.01) is None


def test_get_latest_discards_older_frames():
    q = BoundedFrameQueue(maxsize=5)
    for i in range(4):
        q.put(_frame(i))
    assert q.get_latest(0).seq == 3
    assert len(q) == 0 and q.dropped == 3


def test_backoff_schedule_caps_at_30s():
    b = Backoff()
    assert [b.next_delay() for _ in range(7)] == [1, 2, 5, 10, 30, 30, 30]
    b.reset()
    assert b.next_delay() == 1


def test_backoff_ready_is_non_blocking():
    now = [100.0]
    b = Backoff(clock=lambda: now[0])
    assert b.ready()
    b.next_delay()
    assert not b.ready()
    now[0] += 1.01
    assert b.ready()


def test_worker_survives_exceptions():
    calls = []

    class Flaky(Worker):
        def step(self):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("boom")
            self.sleep(0.01)

    w = Flaky("flaky")
    w._error_backoff = Backoff(schedule=(0.01,))
    w.start()
    time.sleep(0.2)
    w.stop()
    assert len(calls) > 2 and w.last_error == "RuntimeError: boom"
    assert not any(t.name == "flaky" for t in threading.enumerate())
