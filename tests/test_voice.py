from pathlib import Path


ROOT = Path(__file__).parents[1]
ASSISTANT_TEMPLATE = (ROOT / "templates" / "assistant.html").read_text(encoding="utf-8")
BASE_TEMPLATE = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")


def test_voice_controls_are_optional_and_accessible():
    assert 'data-voice-input' in ASSISTANT_TEMPLATE
    assert 'aria-label="{{ translate(\'Start voice input\') }}"' in ASSISTANT_TEMPLATE
    assert 'data-voice-status role="status" aria-live="polite"' in ASSISTANT_TEMPLATE
    assert 'data-assistant-form' in ASSISTANT_TEMPLATE


def test_voice_language_uses_selected_session_language():
    assert "en: 'en-US', te: 'te-IN', hi: 'hi-IN'" in APP_JS
    assert "'language': '{{ current_language }}'" in BASE_TEMPLATE
    assert "recognition.lang = languageCode" in APP_JS


def test_voice_input_reuses_existing_chat_submission():
    assert "questionInput.value = transcript" in APP_JS
    assert "fetch('/api/assistant'" in APP_JS
    assert "body: JSON.stringify({ question, city: cityInput.value })" in APP_JS


def test_voice_fallbacks_are_present():
    assert "window.SpeechRecognition || window.webkitSpeechRecognition" in APP_JS
    assert "i18n.voiceUnsupported" in APP_JS
    assert "event.error === 'not-allowed'" in APP_JS
    assert "window.speechSynthesis" in APP_JS
    assert "i18n.voiceUnavailable" in APP_JS
    assert "utterance.lang = languageCode" in APP_JS
