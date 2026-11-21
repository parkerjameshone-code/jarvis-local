from jarvis_local.memory import Memory


class FakeEmbed:
    VOCAB = ["pizza", "car", "code"]

    def embed(self, model, texts):
        return [[float(t.lower().count(w)) for w in self.VOCAB] + [0.01] for t in texts]


def test_nearest_first(tmp_path):
    m = Memory(tmp_path / "m.db", FakeEmbed())
    m.add("I love pizza pizza", {"a": 1})
    m.add("my car is red")
    m.add("write code")
    res = m.search("pizza please", k=2)
    assert len(res) == 2
    assert res[0][1] == "I love pizza pizza" and res[0][2] == {"a": 1}
    assert res[0][0] > res[1][0]


def test_persists(tmp_path):
    Memory(tmp_path / "m.db", FakeEmbed()).add("car")
    assert Memory(tmp_path / "m.db", FakeEmbed()).search("car")[0][1] == "car"
