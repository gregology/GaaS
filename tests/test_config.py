import yaml

from app.config import YoloAction, _Loader


class TestYoloTag:
    def test_yolo_produces_yolo_action(self):
        raw = yaml.load("action: !yolo unsubscribe", Loader=_Loader)
        assert isinstance(raw["action"], YoloAction)
        assert raw["action"].value == "unsubscribe"

    def test_yolo_in_list(self):
        raw = yaml.load(
            "actions:\n  - !yolo unsubscribe\n  - archive",
            Loader=_Loader,
        )
        assert isinstance(raw["actions"][0], YoloAction)
        assert raw["actions"][0].value == "unsubscribe"
        assert raw["actions"][1] == "archive"

    def test_yolo_equality(self):
        a = YoloAction("unsubscribe")
        b = YoloAction("unsubscribe")
        c = YoloAction("other")
        assert a == b
        assert a != c

    def test_yolo_hash(self):
        a = YoloAction("unsubscribe")
        b = YoloAction("unsubscribe")
        assert hash(a) == hash(b)
        assert {a, b} == {a}
