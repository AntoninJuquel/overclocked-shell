"""Fake write runner shared by action tests."""
from shell.core.bungie import BungieApiError


class FakeActions:
    def __init__(self, errors=None, responses=None):
        self.posts, self.errors, self.responses, self.sleeps = [], list(errors or []), responses or {}, []

    def sleep(self, seconds):
        self.sleeps.append(seconds)

    def post(self, path, body, gap=0.25):
        name = path.rsplit("/", 2)[-2]
        self.posts.append((name, body))
        error = self.errors.pop(0) if self.errors else None
        if error:
            raise BungieApiError(f"Bungie error {error}", error)
        self.sleep(gap)
        queue = self.responses.get(name)
        return queue.pop(0) if queue else None
