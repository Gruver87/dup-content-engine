from content_engine.models import Script
from content_engine.prosody import (
    detect_emotion,
    parse_speaker_line,
    prosody_for,
    resolve_character_voice,
    spoken_and_caption,
)


def test_emotion_explicit_and_cues():
    emo, reason = detect_emotion(text="hello", explicit="joy")
    assert emo == "joy" and reason.startswith("explicit")
    emo2, reason2 = detect_emotion(text="Мне очень страшно в лесу")
    assert emo2 == "fear" and "cue" in reason2
    p = prosody_for(text="ура победа", base_rate="+5%")
    assert p.emotion == "excitement"
    assert p.volume != "+0%" or p.rate != "+5%"


def test_spoken_caption_align():
    spoken, cap = spoken_and_caption("Ой!", speaker="Лиса")
    assert spoken == "Ой!"
    assert cap == "Лиса: Ой!"
    sp, body = parse_speaker_line("Зайка: Спрячемся!")
    assert sp == "Зайка" and body == "Спрячемся!"
    spoken2, cap2 = spoken_and_caption("Зайка: Спрячемся!")
    assert spoken2 == "Спрячемся!"
    assert "Спрячемся" in cap2


def test_character_voice_ru_female():
    v, reason = resolve_character_voice(
        language="ru",
        speaker="Лиса",
        gender="female",
        voice_cfg={"voice_ru": "ru-RU-DmitryNeural"},
    )
    assert "Svetlana" in v or "Female" in v or reason.startswith("gender")
    assert "Svetlana" in v


def test_lines_expand_to_scenes():
    script = Script.from_dict(
        {
            "title": "t",
            "description": "d",
            "language": "ru",
            "tags": ["cartoon"],
            "scenes": [
                {
                    "id": "duo",
                    "visual_query": "cartoon characters",
                    "lines": [
                        {"speaker": "Лиса", "gender": "female", "emotion": "joy", "text": "Привет!"},
                        {"speaker": "Зайка", "gender": "child", "emotion": "fear", "text": "Ой!"},
                    ],
                }
            ],
        }
    )
    assert len(script.scenes) == 2
    assert script.scenes[0].speaker == "Лиса"
    assert script.scenes[1].emotion == "fear"
    assert script.scenes[0].visual_query == "cartoon characters"
