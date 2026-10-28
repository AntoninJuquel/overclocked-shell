"""Fake write runner shared by action tests."""
from shell.core.bungie import BungieApiError


class FakeActions:
    def __init__(self, errors=None, responses=None):
        self.posts, self.errors, self.responses, self.sleeps = [], list(errors or []), list(responses or []), []

    def sleep(self, seconds):
        self.sleeps.append(seconds)

    def post(self, path, body, gap=0.25):
        self.posts.append((path.rsplit("/", 2)[-2], body))
        error = self.errors.pop(0) if self.errors else None
        if error:
            raise BungieApiError(f"Bungie error {error}", error)
        self.sleep(gap)
        return self.responses.pop(0) if self.responses else None
